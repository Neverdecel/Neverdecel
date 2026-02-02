"""Admin routes for analytics dashboard."""

import os
import secrets
from collections.abc import Callable
from functools import wraps

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .storage import AnalyticsStorage

router = APIRouter(prefix="/admin/analytics", tags=["analytics"])

# Admin password from env
ADMIN_PASSWORD = os.getenv("ANALYTICS_PASSWORD", "")


def get_storage(request: Request) -> AnalyticsStorage:
    """Get analytics storage from app state."""
    return request.app.state.analytics_storage


def _check_auth(request: Request) -> bool:
    """Check if request has valid session."""
    session_id = request.cookies.get("analytics_session")
    if not session_id:
        return False
    storage = get_storage(request)
    return storage.validate_admin_session(session_id)


def require_auth(func: Callable):
    """Decorator to require authentication."""

    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        if not _check_auth(request):
            return RedirectResponse(url="/admin/analytics/login", status_code=302)
        return await func(request, *args, **kwargs)

    return wrapper


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = "", locked: str = ""):
    """Render login page."""
    templates = request.app.state.templates
    storage = get_storage(request)
    ip = _get_client_ip(request)

    # Check if locked out
    is_locked, seconds_remaining = storage.is_ip_locked_out(ip)
    if is_locked:
        locked = str(seconds_remaining)

    remaining_attempts = storage.get_remaining_attempts(ip) if not is_locked else 0

    return templates.TemplateResponse(
        request=request,
        name="admin/login.html",
        context={
            "error": error,
            "locked": locked,
            "remaining_attempts": remaining_attempts,
        },
    )


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    """Process login with brute force protection."""
    storage = get_storage(request)
    ip = _get_client_ip(request)

    # Check if locked out
    is_locked, seconds_remaining = storage.is_ip_locked_out(ip)
    if is_locked:
        return RedirectResponse(
            url=f"/admin/analytics/login?locked={seconds_remaining}",
            status_code=302,
        )

    if not ADMIN_PASSWORD:
        return RedirectResponse(
            url="/admin/analytics/login?error=Set+ANALYTICS_PASSWORD+env+var",
            status_code=302,
        )

    if not secrets.compare_digest(password.encode(), ADMIN_PASSWORD.encode()):
        # Record failed attempt
        storage.record_login_attempt(ip, success=False)
        remaining = storage.get_remaining_attempts(ip)

        if remaining == 0:
            return RedirectResponse(
                url="/admin/analytics/login?locked=900",
                status_code=302,
            )

        return RedirectResponse(
            url=f"/admin/analytics/login?error=Invalid+password.+{remaining}+attempts+remaining.",
            status_code=302,
        )

    # Record successful attempt (clears the failed count effectively)
    storage.record_login_attempt(ip, success=True)

    # Create session in persistent storage
    session_id = secrets.token_urlsafe(32)
    storage.create_admin_session(session_id, expires_hours=24)

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
    if session_id:
        storage = get_storage(request)
        storage.delete_admin_session(session_id)

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
    tile_clicks = storage.get_tile_clicks(days=days)
    outbound_clicks = storage.get_outbound_clicks(days=days)

    return templates.TemplateResponse(
        request=request,
        name="admin/analytics.html",
        context={
            "stats": stats,
            "recent": recent,
            "tile_clicks": tile_clicks,
            "outbound_clicks": outbound_clicks,
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


@router.get("/visitors", response_class=HTMLResponse)
@require_auth
async def visitors_list(
    request: Request,
    days: int = 30,
    storage: AnalyticsStorage = Depends(get_storage),
):
    """Render visitors list page."""
    templates = request.app.state.templates
    visitors = storage.get_all_visitors(days=days)

    return templates.TemplateResponse(
        request=request,
        name="admin/visitors.html",
        context={"visitors": visitors, "days": days},
    )


@router.get("/visitor/{visitor_id:path}", response_class=HTMLResponse)
@require_auth
async def visitor_detail(
    request: Request,
    visitor_id: str,
    storage: AnalyticsStorage = Depends(get_storage),
):
    """Render individual visitor detail page."""
    templates = request.app.state.templates
    details = storage.get_visitor_details(visitor_id)

    return templates.TemplateResponse(
        request=request,
        name="admin/visitor_detail.html",
        context={"visitor": details},
    )


@router.post("/api/event")
async def track_event(
    request: Request,
    event: str = Form(...),
    path: str = Form(None),
    metadata: str = Form(None),
    storage: AnalyticsStorage = Depends(get_storage),
):
    """Track a custom event from the frontend."""
    import contextlib
    import json

    # Get visitor IP
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"

    # Parse metadata if provided
    meta_dict = None
    if metadata:
        with contextlib.suppress(json.JSONDecodeError):
            meta_dict = json.loads(metadata)

    storage.record_event(
        event_name=event,
        visitor_id=ip,
        path=path,
        metadata=meta_dict,
    )

    return {"status": "ok"}
