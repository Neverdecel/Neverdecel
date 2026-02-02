"""Neverdecel Portfolio - FastAPI Application."""

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .analytics import AnalyticsMiddleware, AnalyticsStorage
from .analytics.routes import router as analytics_router
from .config import get_settings
from .middleware import SecurityHeadersMiddleware
from .routes import api, pages

# Get project root directory
# main.py is at src/app/main.py, so .parent.parent.parent gets to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_ROOT = Path(__file__).parent.parent

# Initialize settings
settings = get_settings()

# Initialize analytics storage (shared instance for middleware and routes)
_data_dir = PROJECT_ROOT / "data"
_data_dir.mkdir(exist_ok=True)
analytics_storage = AnalyticsStorage(_data_dir / "analytics.db")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - shared resources."""
    # Create shared HTTP client for external API calls
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        headers={"Accept": "application/vnd.github.v3+json"},
    )

    # Store analytics storage reference in app state for routes
    app.state.analytics_storage = analytics_storage

    yield
    # Cleanup on shutdown
    await app.state.http_client.aclose()


# Create FastAPI application
app = FastAPI(
    title="Neverdecel Portfolio",
    description="AI-Native Engineer Portfolio with Ava AI Assistant",
    version="1.0.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan,
)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add analytics tracking middleware (uses shared storage instance)
app.add_middleware(AnalyticsMiddleware, storage=analytics_storage)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://neverdecel.com",
        "https://www.neverdecel.com",
        "http://localhost:9575",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept"],
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
app.include_router(analytics_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "environment": settings.environment}
