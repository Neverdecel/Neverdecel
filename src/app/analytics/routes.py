"""Admin routes for analytics dashboard."""

import hashlib
import os
import secrets
from functools import wraps
from typing import Callable

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from .storage import AnalyticsStorage

router = APIRouter(prefix="/admin/analytics", tags=["analytics"])

# Simple session-based auth
_sessions: set[str] = set()

# Admin password from env or generate one on first run
ADMIN_PASSWORD = os.getenv("ANALYTICS_PASSWORD", "")


def get_storage(request: Request) -> AnalyticsStorage:
    """Get analytics storage from app state."""
    return request.app.state.analytics_storage


def _check_auth(request: Request) -> bool:
    """Check if request has valid session."""
    session_id = request.cookies.get("analytics_session")
    return session_id in _sessions if session_id else False


def require_auth(func: Callable):
    """Decorator to require authentication."""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        if not _check_auth(request):
            return RedirectResponse(url="/admin/analytics/login", status_code=302)
        return await func(request, *args, **kwargs)
    return wrapper


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    """Render login page."""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="admin/login.html",
        context={"error": error},
    )


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    """Process login."""
    # Hash password for comparison
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    expected_hash = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()

    if not ADMIN_PASSWORD:
        # No password set - show setup instructions
        return RedirectResponse(
            url="/admin/analytics/login?error=Set+ANALYTICS_PASSWORD+env+var",
            status_code=302,
        )

    if not secrets.compare_digest(password_hash, expected_hash):
        return RedirectResponse(
            url="/admin/analytics/login?error=Invalid+password",
            status_code=302,
        )

    # Create session
    session_id = secrets.token_urlsafe(32)
    _sessions.add(session_id)

    # Limit sessions
    if len(_sessions) > 100:
        # Remove oldest
        _sessions.pop()

    response = RedirectResponse(url="/admin/analytics", status_code=302)
    response.set_cookie(
        key="analytics_session",
        value=session_id,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=86400,  # 24 hours
    )
    return response


@router.get("/logout")
async def logout(request: Request):
    """Log out and clear session."""
    session_id = request.cookies.get("analytics_session")
    if session_id and session_id in _sessions:
        _sessions.discard(session_id)

    response = RedirectResponse(url="/admin/analytics/login", status_code=302)
    response.delete_cookie("analytics_session")
    return response


@router.get("", response_class=HTMLResponse)
@require_auth
async def dashboard(
    request: Request,
    days: int = 30,
    storage: AnalyticsStorage = Depends(get_storage),
):
    """Render analytics dashboard."""
    templates = request.app.state.templates

    # Get stats
    stats = storage.get_stats(days=days)
    recent = storage.get_recent_visitors(limit=30)

    return templates.TemplateResponse(
        request=request,
        name="admin/analytics.html",
        context={
            "stats": stats,
            "recent": recent,
            "days": days,
        },
    )


@router.get("/api/stats")
@require_auth
async def api_stats(
    request: Request,
    days: int = 30,
    storage: AnalyticsStorage = Depends(get_storage),
):
    """Get stats as JSON for HTMX updates."""
    return storage.get_stats(days=days)


@router.get("/api/recent")
@require_auth
async def api_recent(
    request: Request,
    limit: int = 50,
    storage: AnalyticsStorage = Depends(get_storage),
):
    """Get recent visitors as JSON."""
    return storage.get_recent_visitors(limit=limit)


@router.post("/api/event")
async def track_event(
    request: Request,
    event: str = Form(...),
    path: str = Form(None),
    storage: AnalyticsStorage = Depends(get_storage),
):
    """Track a custom event from the frontend."""
    # Get visitor hash
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"

    # Create visitor hash (must match middleware logic)
    from datetime import datetime
    today = datetime.utcnow().strftime("%Y-%m-%d")
    salt = hashlib.sha256(f"neverdecel-{today}-secret".encode()).hexdigest()
    visitor_hash = hashlib.sha256(f"{ip}-{salt}".encode()).hexdigest()[:16]

    storage.record_event(
        event_name=event,
        visitor_hash=visitor_hash,
        path=path,
    )

    return {"status": "ok"}
