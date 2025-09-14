from abc import ABC, abstractmethod
import requests
import json
import os
import re
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

class EchoDataExtractor(ABC):
    """Abstract base class for extracting ECHO data from different report formats"""
    
    @abstractmethod
    def extract_echo_url(self, raw_text: str) -> str:
        """Extract ECHO URL from raw text for specific report format"""
        pass
    
    @abstractmethod
    def get_url_label(self) -> str:
        """Get the label used in the report for the ECHO URL"""
        pass

class EchoDataProcessor(ABC):
    """Abstract base class for processing ECHO data"""
    
    @abstractmethod
    def process_echo_data(self, echo_data: str) -> str:
        """Process raw ECHO data into formatted summary"""
        pass

class BaseEchoService:
    """Base service with shared ECHO functionality"""
    
    # Configuration
    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
    CLAUDE_API_KEY = os.getenv("CLAUDE")
    FIRECRAWL_ENDPOINT = "https://api.firecrawl.dev/v1/scrape"
    ECHO_API_KEY = os.getenv("ECHO_API")
    
    @staticmethod
    def scrape_with_delay(target_url: str, delay_ms: int = 5000):
        """Scrape URL using Firecrawl API"""
        headers = {
            "Authorization": f"Bearer {BaseEchoService.ECHO_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "url": target_url,
            "onlyMainContent": True,
            "waitFor": delay_ms,
            "timeout": 30000,
            "formats": ["markdown"],
        }

        resp = requests.post(BaseEchoService.FIRECRAWL_ENDPOINT, json=payload, headers=headers)
        resp.raise_for_status()
        result = resp.json()

        return result.get("data", {}).get("markdown")
    
    @staticmethod
    def get_echo_data_by_url(echo_url: str):
        """Get ECHO compliance data using URL"""
        print(f"Fetching ECHO data from: {echo_url}")
        
        try:
            compliance_data = BaseEchoService.scrape_with_delay(echo_url, delay_ms=10000)
            
            if compliance_data:
                print("ECHO data retrieved successfully")
                return compliance_data
            else:
                print("No data found at URL")
                return None
                
        except Exception as e:
            print(f"Error fetching ECHO data: {str(e)}")
            return None

# EDR Report ECHO Extractor
class EDREchoExtractor(EchoDataExtractor):
    """Extract ECHO URLs from EDR reports"""
    
    def extract_echo_url(self, raw_text: str) -> str:
        """Extract DFR URL from EDR report format"""
        patterns = [
            r'DFR URL:\s*(https?://echo\.epa\.gov/detailed-facility-report\?[^\s\n]+)',
            r'DFR URL:\s*(http://echo\.epa\.gov/detailed-facility-report\?[^\s\n]+)',
            r'DFR URL:\s*(http://oaspub\.epa\.gov/enviro/[^\s\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def get_url_label(self) -> str:
        return "DFR URL"

# ERIS Report ECHO Extractor
class ERISEchoExtractor(EchoDataExtractor):
    """Extract ECHO URLs from ERIS reports"""
    
    def extract_echo_url(self, raw_text: str) -> str:
        """Extract ECHO Facility Report URL from ERIS report format"""
        patterns = [
            r'ECHO Facility Report:\s*(https?://echo\.epa\.gov/detailed-facility-report\?[^\s\n]+)',
            # r'Facility Detail Rprt URL:\s*(https://ofmpub\.epa\.gov/frs_public2/fii_query_detail\.disp_program_facility\?[^\s\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def get_url_label(self) -> str:
        return "ECHO Facility Report"

# Claude-based ECHO Processor
class ClaudeEchoProcessor(EchoDataProcessor):
    """Process ECHO data using Claude AI"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or BaseEchoService.CLAUDE_API_KEY
        if not self.api_key:
            raise ValueError("Claude API key not found. Set CLAUDE or ANTHROPIC_API_KEY environment variable.")
    
    def process_echo_data(self, echo_data: str) -> str:
        """Process ECHO data with Claude using standardized prompt"""
        
        # Standardized ECHO processing prompt
        prompt_base = """Role

You are a data formatting assistant.

Task

Your task is to summarize the compliance history for addresses found in the EPA ECHO database. Each property will have its own separate list. You will ONLY output the lists and not add any filler text.

Guidelines

Follow these guidelines to create the lists:

List Structure:
#Header: Property Name and Address
List: Details

ONLY include the following specific details in the lists:
- Summarize the inspection, enforcement, and compliance history of each address

Below is the extracted EPA ECHO data that you need to analyze and format:

---BEGIN ECHO DATA---"""
        
        full_prompt = f"{prompt_base}\n{echo_data}\n---END ECHO DATA---"
        
        # Claude API call
        endpoint = "https://api.anthropic.com/v1/messages"
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        
        body = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4000,
            "messages": [
                {
                    "role": "user",
                    "content": full_prompt
                }
            ]
        }
        
        try:
            response = requests.post(endpoint, headers=headers, json=body)
            
            if response.status_code == 200:
                response_data = response.json()
                return response_data['content'][0]['text']
            else:
                error_msg = f"Claude API error {response.status_code}: {response.text}"
                print(error_msg)
                return f"Error: {error_msg}"
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            print(error_msg)
            return f"Error: {error_msg}"
        
        except KeyError as e:
            error_msg = f"Unexpected response format: {str(e)}"
            print(error_msg)
            return f"Error: {error_msg}"
        
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON response: {str(e)}"
            print(error_msg)
            return f"Error: {error_msg}"

# Complete ECHO Service
class EchoComplianceService:
    """Main service that orchestrates ECHO data extraction and processing"""
    
    def __init__(self, extractor: EchoDataExtractor, processor: EchoDataProcessor):
        self.extractor = extractor
        self.processor = processor
    
    def get_compliance_summary(self, raw_text: str) -> str:
        """Complete workflow: extract URL, fetch data, process with AI"""
        
        # Step 1: Extract ECHO URL from raw text
        echo_url = self.extractor.extract_echo_url(raw_text)
        
        if not echo_url:
            print(f"No {self.extractor.get_url_label()} found in raw text")
            return None
        
        print(f"Found {self.extractor.get_url_label()}: {echo_url}")
        
        # Step 2: Fetch ECHO data
        echo_raw_data = BaseEchoService.get_echo_data_by_url(echo_url)
        
        if not echo_raw_data:
            print("No ECHO data retrieved from API")
            return None
        
        # Step 3: Process with AI
        print("Processing ECHO data with AI...")
        echo_summary = self.processor.process_echo_data(echo_raw_data)
        
        return echo_summary

# Factory for creating ECHO services
class EchoServiceFactory:
    """Factory for creating appropriate ECHO services based on report type"""
    
    @staticmethod
    def create_service(report_type: str) -> EchoComplianceService:
        """Create ECHO service for specific report type"""
        
        # Create appropriate extractor and processor based on report type
        if report_type.upper() == "EDR":
            extractor = EDREchoExtractor()
            processor = ClaudeEchoProcessor()  # Remove the file path argument
        elif report_type.upper() == "ERIS":
            extractor = ERISEchoExtractor()
            processor = ClaudeEchoProcessor()  # Remove the file path argument
        else:
            raise ValueError(f"Unknown report type: {report_type}")
        
        return EchoComplianceService(extractor, processor)