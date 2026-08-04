import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import Config
from src.routes.meetings import router as meetings_router

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ai_meeting_summarizer")

# Initialize FastAPI application
app = FastAPI(
    title="AI Meeting Summarizer API",
    description=(
        "Production-grade meeting intelligence platform powered by FastAPI and Google Gemini 2.5. "
        "Transcribes meeting audio, extracts grounded action items and decisions (with source excerpts), "
        "and drafts ready-to-send follow-up emails."
    ),
    version="0.1.0",
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(meetings_router)


# Global Health Check
@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint confirming API service and configuration status."""
    try:
        cfg = Config(check_keys=False)
        has_key = bool(cfg.gemini_api_key)
        return {
            "status": "healthy" if has_key else "warning",
            "gemini_api_key_configured": has_key,
            "model": cfg.gemini_model,
        }
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "unhealthy", "detail": str(exc)},
        )


@app.get("/", tags=["Root"])
def root():
    return {
        "name": "AI Meeting Summarizer API",
        "version": "0.1.0",
        "docs_url": "/docs",
    }
