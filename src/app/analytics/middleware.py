"""Analytics tracking middleware for FastAPI."""

import logging
import time

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

    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP from request."""
        # Debug: log all IP-related headers
        cf_ip = request.headers.get("cf-connecting-ip")
        forwarded = request.headers.get("x-forwarded-for")
        real_ip = request.headers.get("x-real-ip")
        client_host = request.client.host if request.client else None

        logger.info(
            "IP headers - CF-Connecting-IP: %s, X-Forwarded-For: %s, "
            "X-Real-IP: %s, client.host: %s",
            cf_ip,
            forwarded,
            real_ip,
            client_host,
        )

        # Cloudflare-specific header (most reliable when using CF tunnel)
        if cf_ip:
            return cf_ip.strip()

        # Check X-Forwarded-For (may contain multiple IPs)
        if forwarded:
            # Take first IP (original client)
            return forwarded.split(",")[0].strip()

        if real_ip:
            return real_ip.strip()

        # Fall back to direct connection
        if client_host:
            return client_host

        return "unknown"

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
        return request.method in ("GET", "POST")

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
            user_agent = request.headers.get("user-agent", "")
            referrer = request.headers.get("referer")  # Note: HTTP uses "referer"
            path = request.url.path

            # Parse user agent
            parsed_ua = parse_user_agent(user_agent)

            # Extract referrer domain and filter self-referrals
            referrer_domain = extract_domain(referrer) if referrer else None
            if referrer_domain and "neverdecel" in referrer_domain:
                referrer = None
                referrer_domain = None

            # Extract UTM parameters
            query_params = dict(request.query_params)
            utm_source = query_params.get("utm_source")
            utm_medium = query_params.get("utm_medium")
            utm_campaign = query_params.get("utm_campaign")
            utm_content = query_params.get("utm_content")
            utm_term = query_params.get("utm_term")

            # Geo lookup
            geo = None
            try:
                http_client = getattr(request.app.state, "http_client", None)
                geo = await lookup_ip(ip, http_client)
            except Exception as e:
                logger.debug("Geo lookup skipped: %s", e)

            # Record pageview
            self.storage.record_pageview(
                path=path,
                visitor_id=ip,
                referrer=referrer,
                referrer_domain=referrer_domain,
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
                utm_source=utm_source,
                utm_medium=utm_medium,
                utm_campaign=utm_campaign,
                utm_content=utm_content,
                utm_term=utm_term,
            )

        except Exception as e:
            # Never let analytics break the site
            logger.error("Analytics tracking error: %s", e)

        return response
