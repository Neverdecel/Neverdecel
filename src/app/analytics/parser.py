"""User-agent parsing and bot detection."""

import re
from dataclasses import dataclass

# Common bot patterns
BOT_PATTERNS = [
    r"bot",
    r"crawl",
    r"spider",
    r"slurp",
    r"search",
    r"fetch",
    r"scrape",
    r"wget",
    r"curl",
    r"python-requests",
    r"python-urllib",
    r"java",
    r"perl",
    r"ruby",
    r"go-http",
    r"apache-httpclient",
    r"googlebot",
    r"bingbot",
    r"yandex",
    r"baidu",
    r"duckduck",
    r"facebook",
    r"twitter",
    r"whatsapp",
    r"telegram",
    r"slack",
    r"discord",
    r"linkedin",
    r"pinterest",
    r"semrush",
    r"ahrefs",
    r"mj12bot",
    r"dotbot",
    r"petalbot",
    r"bytespider",
    r"gptbot",
    r"claudebot",
    r"anthropic",
    r"openai",
    r"chatgpt",
    r"headless",
    r"phantom",
    r"selenium",
    r"puppeteer",
    r"playwright",
    r"lighthouse",
    r"pagespeed",
    r"gtmetrix",
    r"pingdom",
    r"uptime",
    r"monitor",
    r"health",
    r"probe",
    r"check",
]

BOT_REGEX = re.compile("|".join(BOT_PATTERNS), re.IGNORECASE)

# Browser detection patterns
BROWSER_PATTERNS = [
    (r"Firefox/(\d+)", "Firefox"),
    (r"Edg/(\d+)", "Edge"),
    (r"OPR/(\d+)", "Opera"),
    (r"Opera/(\d+)", "Opera"),
    (r"Chrome/(\d+)", "Chrome"),
    (r"Safari/(\d+)", "Safari"),
    (r"MSIE (\d+)", "Internet Explorer"),
    (r"Trident/.*rv:(\d+)", "Internet Explorer"),
]

# OS detection patterns
OS_PATTERNS = [
    (r"Windows NT 10\.0", "Windows 10/11"),
    (r"Windows NT 6\.3", "Windows 8.1"),
    (r"Windows NT 6\.2", "Windows 8"),
    (r"Windows NT 6\.1", "Windows 7"),
    (r"Windows", "Windows"),
    (r"Mac OS X (\d+[._]\d+)", "macOS"),
    (r"Macintosh", "macOS"),
    (r"Android (\d+)", "Android"),
    (r"iPhone OS (\d+)", "iOS"),
    (r"iPad.*OS (\d+)", "iPadOS"),
    (r"Linux", "Linux"),
    (r"CrOS", "ChromeOS"),
    (r"Ubuntu", "Ubuntu"),
    (r"Fedora", "Fedora"),
]

# Device type patterns
MOBILE_PATTERNS = [
    r"Mobile",
    r"Android",
    r"iPhone",
    r"iPod",
    r"BlackBerry",
    r"Windows Phone",
    r"Opera Mini",
    r"Opera Mobi",
]

TABLET_PATTERNS = [
    r"iPad",
    r"Tablet",
    r"PlayBook",
    r"Silk",
]


@dataclass
class ParsedUserAgent:
    """Parsed user agent information."""

    browser: str | None
    browser_version: str | None
    os: str | None
    device_type: str
    is_bot: bool
    raw: str


def parse_user_agent(ua: str | None) -> ParsedUserAgent:
    """Parse a user agent string into components."""
    if not ua:
        return ParsedUserAgent(
            browser=None,
            browser_version=None,
            os=None,
            device_type="unknown",
            is_bot=False,
            raw="",
        )

    # Check for bot
    is_bot = bool(BOT_REGEX.search(ua))

    # Detect browser
    browser = None
    browser_version = None
    for pattern, name in BROWSER_PATTERNS:
        match = re.search(pattern, ua)
        if match:
            browser = name
            browser_version = match.group(1)
            break

    # Detect OS
    os_name = None
    for pattern, name in OS_PATTERNS:
        if re.search(pattern, ua):
            os_name = name
            break

    # Detect device type
    device_type = "desktop"
    if any(re.search(p, ua, re.IGNORECASE) for p in TABLET_PATTERNS):
        device_type = "tablet"
    elif any(re.search(p, ua, re.IGNORECASE) for p in MOBILE_PATTERNS):
        device_type = "mobile"

    return ParsedUserAgent(
        browser=browser,
        browser_version=browser_version,
        os=os_name,
        device_type=device_type,
        is_bot=is_bot,
        raw=ua,
    )


def extract_domain(url: str | None) -> str | None:
    """Extract domain from a URL for cleaner referrer display."""
    if not url:
        return None

    # Remove protocol
    url = re.sub(r"^https?://", "", url)

    # Remove www.
    url = re.sub(r"^www\.", "", url)

    # Get domain only (remove path)
    domain = url.split("/")[0]

    # Remove port
    domain = domain.split(":")[0]

    return domain if domain else None
