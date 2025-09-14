# extract_summarize/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)

# Import routers from local package
from routers import testing

def create_app() -> FastAPI:
    app = FastAPI(
        title="Environmental Assessment Assistant",
        version="2.0.0",
        description="Modular PDF → Extraction → Format → Summarize system for EDR and ERIS environmental reports with ECHO compliance integration.",
    )

    # CORS - Updated for Lovable integration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "*",  # Allow all origins for development - tighten in production
            "https://lovable.dev",
            "https://*.lovable.dev",
            "https://phase1-production-2a06.up.railway.app",
            "http://localhost:3000",
            "http://localhost:8000",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(testing.router)

    @app.get("/", tags=["meta"])
    def root():
        return {
            "name": "Environmental Assessment Assistant",
            "version": "2.0.0",
            "description": "Modular system for EDR and ERIS environmental reports",
            "docs": "/docs",
            "health": "/healthz",
            "api_endpoints": {
                "websocket": "/testing/realtest",
                "rest_api": {
                    "upload_pdf": "/testing/api/upload-pdf",
                    "generate_section": "/testing/api/generate-section", 
                    "chat": "/testing/api/chat",
                    "session": "/testing/api/session/{session_id}"
                }
            },
            "features": [
                "EDR Report Generation (Sections 5.2.1 & 5.2.2)",
                "ERIS Report Generation (Sections 5.2.3 & 5.2.4)", 
                "EPA ECHO Compliance Integration",
                "Modular Text Extraction (Poppler)",
                "Distance Calculation (Precisely API)",
                "Real-time WebSocket Interface",
                "REST API for Frontend Integration"
            ]
        }

    @app.get("/healthz", tags=["meta"])
    def healthz():
        return {
            "status": "healthy",
            "version": "2.0.0",
            "services": {
                "text_extraction": "active",
                "formatting": "active", 
                "summarization": "active",
                "echo_compliance": "active",
                "distance_calculation": "active",
                "websocket": "active",
                "rest_api": "active"
            }
        }

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8000))
    logging.info(f"Starting Environmental Assessment Assistant on port {port}")
    logging.info("Available report types: EDR (5.2.1/5.2.2) and ERIS (5.2.3/5.2.4)")
    logging.info("API Endpoints: WebSocket + REST API for frontend integration")
    
    uvicorn.run(app, host="0.0.0.0", port=port)