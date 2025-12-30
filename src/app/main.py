"""Neverdecel Portfolio - FastAPI Application."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .routes import api, pages

# Get project root directory
# main.py is at src/app/main.py, so .parent.parent.parent gets to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_ROOT = Path(__file__).parent.parent

# Initialize settings
settings = get_settings()

# Create FastAPI application
app = FastAPI(
    title="Neverdecel Portfolio",
    description="DevOps & AI Engineer Portfolio with Ava AI Assistant",
    version="1.0.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# Mount static files
app.mount("/static", StaticFiles(directory=SRC_ROOT / "static"), name="static")
app.mount("/image", StaticFiles(directory=PROJECT_ROOT / "image"), name="image")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=SRC_ROOT / "templates")

# Store templates in app state for access in routes
app.state.templates = templates

# Include routers
app.include_router(pages.router)
app.include_router(api.router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "environment": settings.environment}
