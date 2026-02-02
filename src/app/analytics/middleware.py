"""Analytics tracking middleware for FastAPI."""

import hashlib
import logging
import time
from datetime import datetime

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .geo import lookup_ip
from .parser import extract_domain, parse_user_agent
from .storage import AnalyticsStorage

logger = logging.getLogger(__name__)

# Paths to exclude from tracking
EXCLUDED_PATHS = {
    "/health",
    "/favicon.ico",
    "/robots.txt",
    "/sitemap.xml",
}

EXCLUDED_PREFIXES = (
    "/static/",
    "/image/",
    "/admin/analytics",  # Don't track admin views
    "/_",  # Internal routes
)


class AnalyticsMiddleware(BaseHTTPMiddleware):
    """Middleware to track all incoming requests."""

    def __init__(self, app, storage: AnalyticsStorage | None = None):
        super().__init__(app)
        self.storage = storage or AnalyticsStorage()
        # Daily rotating salt for visitor hashing
        self._salt_date: str = ""
        self._salt: str = ""

    def _get_salt(self) -> str:
        """Get daily rotating salt for visitor hashing."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if today != self._salt_date:
            # Generate new salt for the day
            self._salt = hashlib.sha256(f"neverdecel-{today}-secret".encode()).hexdigest()
            self._salt_date = today
        return self._salt

    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP from request."""
        # Check common proxy headers
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Take first IP (original client)
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            return cf_ip.strip()

        # Fall back to direct connection
        if request.client:
            return request.client.host

        return "unknown"

    def _hash_visitor(self, ip: str) -> str:
        """Create a privacy-safe visitor hash."""
        salt = self._get_salt()
        raw = f"{ip}-{salt}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _should_track(self, request: Request) -> bool:
        """Determine if this request should be tracked."""
        path = request.url.path

        # Skip excluded exact paths
        if path in EXCLUDED_PATHS:
            return False

        # Skip excluded prefixes
        if path.startswith(EXCLUDED_PREFIXES):
            return False

        # Skip non-GET/POST methods (OPTIONS, HEAD, etc.)
        if request.method not in ("GET", "POST"):
            return False

        return True

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and track analytics."""
        # Check if we should track this request
        if not self._should_track(request):
            return await call_next(request)

        start_time = time.perf_counter()

        # Get response first
        response = await call_next(request)

        # Calculate response time
        response_time_ms = int((time.perf_counter() - start_time) * 1000)

        # Extract request info
        try:
            ip = self._get_client_ip(request)
            visitor_hash = self._hash_visitor(ip)
            user_agent = request.headers.get("user-agent", "")
            referrer = request.headers.get("referer")  # Note: HTTP uses "referer"
            path = request.url.path

            # Parse user agent
            parsed_ua = parse_user_agent(user_agent)

            # Extract referrer domain
            referrer_domain = extract_domain(referrer) if referrer else None
            # Don't track self-referrals
            if referrer_domain and "neverdecel" in referrer_domain:
                referrer_domain = None

            # Geo lookup (async, but we don't await to avoid blocking)
            # For now, do a quick sync-ish lookup or skip
            geo = None
            try:
                # Use app's shared HTTP client if available
                http_client = getattr(request.app.state, "http_client", None)
                geo = await lookup_ip(ip, http_client)
            except Exception as e:
                logger.debug("Geo lookup skipped: %s", e)

            # Record pageview
            self.storage.record_pageview(
                path=path,
                visitor_hash=visitor_hash,
                ip_address=ip,  # Store for debugging, can remove for stricter privacy
                referrer=referrer_domain,
                country=geo.country if geo else None,
                city=geo.city if geo else None,
                user_agent=user_agent[:500],  # Truncate long UAs
                browser=parsed_ua.browser,
                browser_version=parsed_ua.browser_version,
                os=parsed_ua.os,
                device_type=parsed_ua.device_type,
                is_bot=parsed_ua.is_bot,
                response_time_ms=response_time_ms,
                status_code=response.status_code,
            )

        except Exception as e:
            # Never let analytics break the site
            logger.error("Analytics tracking error: %s", e)

        return response
