"""IP geolocation using free ip-api.com service."""

import asyncio
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class GeoInfo:
    """Geographic information from IP lookup."""
    country: str | None
    country_code: str | None
    region: str | None
    city: str | None
    lat: float | None
    lon: float | None
    isp: str | None
    is_proxy: bool
    is_hosting: bool


# In-memory cache for geo lookups
_geo_cache: dict[str, GeoInfo] = {}
_cache_lock = asyncio.Lock()

# Private/local IP ranges that shouldn't be looked up
PRIVATE_IP_PREFIXES = (
    "127.", "10.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
    "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
    "192.168.", "::1", "fe80:", "fc00:", "fd00:", "localhost",
)


def is_private_ip(ip: str) -> bool:
    """Check if an IP address is private/local."""
    return ip.startswith(PRIVATE_IP_PREFIXES) or ip == "unknown"


async def lookup_ip(ip: str, client: httpx.AsyncClient | None = None) -> GeoInfo:
    """
    Look up geographic information for an IP address.
    Uses ip-api.com (free, 45 requests/minute for non-commercial).
    """
    # Return empty for private IPs
    if is_private_ip(ip):
        return GeoInfo(
            country=None, country_code=None, region=None, city=None,
            lat=None, lon=None, isp=None, is_proxy=False, is_hosting=False,
        )

    # Check cache
    async with _cache_lock:
        if ip in _geo_cache:
            return _geo_cache[ip]

    try:
        # Use provided client or create temporary one
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=5.0)
            should_close = True

        try:
            # ip-api.com free tier (no API key needed)
            # Fields: country, countryCode, region, city, lat, lon, isp, proxy, hosting
            response = await client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "country,countryCode,region,city,lat,lon,isp,proxy,hosting"},
            )

            if response.status_code == 200:
                data = response.json()

                geo = GeoInfo(
                    country=data.get("country"),
                    country_code=data.get("countryCode"),
                    region=data.get("region"),
                    city=data.get("city"),
                    lat=data.get("lat"),
                    lon=data.get("lon"),
                    isp=data.get("isp"),
                    is_proxy=data.get("proxy", False),
                    is_hosting=data.get("hosting", False),
                )

                # Cache the result
                async with _cache_lock:
                    # Limit cache size
                    if len(_geo_cache) > 10000:
                        # Clear oldest half
                        keys = list(_geo_cache.keys())[:5000]
                        for k in keys:
                            del _geo_cache[k]
                    _geo_cache[ip] = geo

                return geo

        finally:
            if should_close:
                await client.aclose()

    except httpx.TimeoutException:
        logger.debug("Geo lookup timeout for %s", ip[:8])
    except Exception as e:
        logger.debug("Geo lookup failed for %s: %s", ip[:8], e)

    # Return empty on failure
    return GeoInfo(
        country=None, country_code=None, region=None, city=None,
        lat=None, lon=None, isp=None, is_proxy=False, is_hosting=False,
    )


@lru_cache(maxsize=256)
def get_country_flag(country_code: str | None) -> str:
    """Get emoji flag for a country code."""
    if not country_code or len(country_code) != 2:
        return ""

    # Convert country code to regional indicator symbols
    return "".join(chr(ord(c) + 127397) for c in country_code.upper())
