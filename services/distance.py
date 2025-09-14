"""
Distance calculation service for environmental assessment reports.
Calculates distances and directions between subject property and surrounding properties.
"""

from abc import ABC, abstractmethod
import os
import time
import requests
from typing import Dict, List, Tuple, Optional
from shapely.geometry import shape
from shapely.ops import nearest_points
from geographiclib.geodesic import Geodesic
from dotenv import load_dotenv

load_dotenv()

class DistanceCalculator(ABC):
    """Abstract base class for distance calculation services"""
    
    @abstractmethod
    def calculate_distances(self, subject_address: str, surrounding_addresses: List[str]) -> Dict:
        """Calculate distances between subject property and surrounding properties"""
        pass

class GeocodeService(ABC):
    """Abstract base class for geocoding services"""
    
    @abstractmethod
    def get_geometry(self, address: str) -> Optional[Dict]:
        """Get geometry for an address"""
        pass

class PreciselyGeocodeService(GeocodeService):
    """Precisely API geocoding service"""
    
    def __init__(self, client_id: str = None, client_secret: str = None):
        self.client_id = client_id or os.getenv("PRECISELY_CLIENT_ID", "mWf9rmwOkL36767kksvAVianIyuohzW8")
        self.client_secret = client_secret or os.getenv("PRECISELY_CLIENT_SECRET", "63Ma28PxCGId1xrw")
        self.auth_url = "https://api.precisely.com/oauth/token"
        self.api_url = "https://api.precisely.com/property/v2/parcelboundary/byaddress"
        self.token_manager = self._create_token_manager()
    
    def _create_token_manager(self):
        """Create token manager for OAuth authentication"""
        return TokenManager(self.auth_url, self.client_id, self.client_secret)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers"""
        return {"Authorization": f"Bearer {self.token_manager.get_token()}"}
    
    def get_geometry(self, address: str) -> Optional[Dict]:
        """Get geometry for an address using Precisely API"""
        try:
            response = requests.get(
                self.api_url, 
                params={"address": address}, 
                headers=self._get_headers(), 
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            # Try to get geometry first
            geom = data.get("geometry")
            if geom and isinstance(geom.get("coordinates"), list):
                return geom

            # Fallback to center coordinates
            center = data.get("center", {})
            coords = center.get("coordinates")
            
            if isinstance(coords, dict):
                lon = coords.get("x") or coords.get("longitude")
                lat = coords.get("y") or coords.get("latitude")
                coords = [lon, lat]
            
            if isinstance(coords, (list, tuple)) and len(coords) == 2:
                return {
                    "type": center.get("type", "Point"),
                    "coordinates": [float(coords[0]), float(coords[1])]
                }
            
            return None
            
        except Exception as e:
            print(f"Geocoding failed for {address}: {e}")
            return None

class TokenManager:
    """OAuth2 token manager for API authentication"""
    
    def __init__(self, auth_url: str, client_id: str, client_secret: str):
        self.auth_url = auth_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.expiry = 0.0

    def get_token(self) -> str:
        """Get or refresh authentication token"""
        now = time.time()
        if self.token is None or now >= (self.expiry - 60):
            response = requests.post(
                self.auth_url,
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            self.token = data.get("access_token")
            self.expiry = now + float(data.get("expiresIn", data.get("expires_in", 3600)))
        return self.token

class GeographicCalculator:
    """Helper class for geographic calculations"""
    
    @staticmethod
    def distance_and_direction(geometry1: Dict, geometry2: Dict, 
                             zero_threshold_m: float = 1.0, 
                             compass_points: int = 8) -> Tuple[float, float, str]:
        """Calculate distance and direction between two geometries"""
        g1 = shape(geometry1)
        g2 = shape(geometry2)

        # Get nearest points between geometries
        p1, p2 = nearest_points(g1, g2)
        inv = Geodesic.WGS84.Inverse(p1.y, p1.x, p2.y, p2.x)
        distance_m = inv["s12"]

        if distance_m >= zero_threshold_m:
            bearing = (inv["azi1"] + 360.0) % 360.0
            return distance_m, bearing, GeographicCalculator._compass_label(bearing, compass_points)

        # Fallback for touching/overlapping geometries
        r1 = g1.representative_point()
        r2 = g2.representative_point()
        bearing = GeographicCalculator._azimuth_degrees(r1.y, r1.x, r2.y, r2.x)
        inv2 = Geodesic.WGS84.Inverse(r1.y, r1.x, r2.y, r2.x)
        return inv2["s12"], bearing, GeographicCalculator._compass_label(bearing, compass_points)

    @staticmethod
    def _azimuth_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate azimuth between two points"""
        inv = Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2)
        return (inv["azi1"] + 360.0) % 360.0

    @staticmethod
    def _compass_label(bearing_degrees: float, num_points: int = 8) -> str:
        """Convert bearing to compass direction label"""
        if num_points == 8:
            names = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        else:
            names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", 
                    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        
        sector = round(bearing_degrees / (360.0 / len(names))) % len(names)
        return names[sector]

class PreciselyDistanceCalculator(DistanceCalculator):
    """Distance calculator using Precisely geocoding service"""
    
    def __init__(self, geocode_service: GeocodeService = None):
        self.geocode_service = geocode_service or PreciselyGeocodeService()
        self.geo_calculator = GeographicCalculator()
    
    def calculate_distances(self, subject_address: str, surrounding_addresses: List[str]) -> Dict:
        """Calculate distances between subject property and surrounding properties"""
        
        # Get subject property geometry
        subject_geometry = self.geocode_service.get_geometry(subject_address)
        if not subject_geometry:
            raise RuntimeError(f"Could not geocode subject address: {subject_address}")
        
        results = []
        failed = []
        
        for address in surrounding_addresses:
            # Get surrounding property geometry
            geometry = self.geocode_service.get_geometry(address)
            if not geometry:
                failed.append({
                    "address": address,
                    "error": "Geocoding failed"
                })
                continue
            
            # Calculate distance and direction
            try:
                distance_m, bearing_deg, direction = self.geo_calculator.distance_and_direction(
                    subject_geometry, geometry
                )
                
                results.append({
                    "address": address,
                    "distance_ft": round(distance_m * 3.28084, 1),  # Convert to feet, round to 1 decimal
                    "direction": direction,
                    "bearing_deg": round(bearing_deg, 1)
                })
                
            except Exception as e:
                failed.append({
                    "address": address,
                    "error": f"Distance calculation failed: {str(e)}"
                })
        
        return {
            "subject_address": subject_address,
            "distances": results,
            "failed": failed
        }

class DistanceCalculatorFactory:
    """Factory for creating distance calculators"""
    
    @staticmethod
    def create_calculator(service_type: str = "precisely") -> DistanceCalculator:
        """Create distance calculator for specified service type"""
        if service_type.lower() == "precisely":
            return PreciselyDistanceCalculator()
        else:
            raise ValueError(f"Unknown distance calculator type: {service_type}")