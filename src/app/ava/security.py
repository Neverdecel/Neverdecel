"""Security utilities for Ava AI Agent."""

import html
import re
import time
from collections import defaultdict

# Rate limiting configuration
RATE_LIMIT_REQUESTS = 10  # Max requests per window
RATE_LIMIT_WINDOW = 60  # Window in seconds (1 minute)
RATE_LIMIT_COOLDOWN = 300  # Cooldown after limit hit (5 minutes)

# Input validation
MAX_MESSAGE_LENGTH = 500  # Max characters per message
MIN_MESSAGE_LENGTH = 1

# Session limits
MAX_SESSIONS = 1000  # Max concurrent sessions in memory
SESSION_TTL = 1800  # Session timeout in seconds (30 minutes)
MAX_MESSAGES_PER_SESSION = 50  # Max messages before session reset

# Rate limiter storage: {ip: {"count": int, "window_start": float, "blocked_until": float}}
_rate_limits: dict = defaultdict(lambda: {"count": 0, "window_start": 0, "blocked_until": 0})

# Patterns that suggest prompt injection attempts
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?)",
    r"forget\s+(everything|all|your)\s+(instructions?|training|prompts?)",
    r"you\s+are\s+(now|no\s+longer)\s+(a|an)",
    r"new\s+(instructions?|persona|role|identity)",
    r"disregard\s+(all\s+)?(previous|prior|your)",
    r"override\s+(your|system|the)\s+(prompt|instructions?)",
    r"pretend\s+(you\s+are|to\s+be)",
    r"act\s+as\s+(if\s+you\s+are|a\s+different)",
    r"jailbreak",
    r"DAN\s+mode",
    r"\[system\]|\[admin\]|\[root\]",
    r"<\s*(system|admin|root)\s*>",
]

# Compiled injection patterns for performance
_compiled_patterns = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def check_rate_limit(ip: str) -> tuple[bool, str | None]:
    """
    Check if an IP is rate limited.

    Returns:
        Tuple of (allowed: bool, error_message: Optional[str])
    """
    now = time.time()
    limit_data = _rate_limits[ip]

    # Check if IP is in cooldown
    if limit_data["blocked_until"] > now:
        remaining = int(limit_data["blocked_until"] - now)
        return False, f"Rate limit exceeded. Try again in {remaining} seconds."

    # Reset window if expired
    if now - limit_data["window_start"] > RATE_LIMIT_WINDOW:
        limit_data["count"] = 0
        limit_data["window_start"] = now

    # Check if limit exceeded
    if limit_data["count"] >= RATE_LIMIT_REQUESTS:
        limit_data["blocked_until"] = now + RATE_LIMIT_COOLDOWN
        return False, f"Rate limit exceeded. Try again in {RATE_LIMIT_COOLDOWN} seconds."

    # Increment counter
    limit_data["count"] += 1
    return True, None


def validate_message(message: str) -> tuple[bool, str | None]:
    """
    Validate and sanitize user message.

    Returns:
        Tuple of (valid: bool, error_message: Optional[str])
    """
    if not message or len(message.strip()) < MIN_MESSAGE_LENGTH:
        return False, "Message cannot be empty."

    if len(message) > MAX_MESSAGE_LENGTH:
        return False, f"Message too long. Maximum {MAX_MESSAGE_LENGTH} characters."

    return True, None


def sanitize_input(message: str) -> str:
    """
    Sanitize user input to prevent injection and control character abuse.
    """
    # Remove null bytes and other control characters (keep newlines and tabs)
    message = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", message)

    # Normalize whitespace (collapse multiple spaces/newlines)
    message = re.sub(r"\n{3,}", "\n\n", message)
    message = re.sub(r" {3,}", "  ", message)

    # Strip leading/trailing whitespace
    return message.strip()


def detect_injection_attempt(message: str) -> tuple[bool, str | None]:
    """
    Detect potential prompt injection attempts.

    Returns:
        Tuple of (is_injection: bool, detected_pattern: Optional[str])
    """
    message_lower = message.lower()

    for pattern in _compiled_patterns:
        if pattern.search(message_lower):
            return True, pattern.pattern

    return False, None


def sanitize_output(response: str) -> str:
    """
    Sanitize AI output to prevent XSS attacks.
    Escapes HTML entities while preserving intended formatting.
    """
    # Escape HTML entities
    escaped = html.escape(response)

    # Convert newlines to <br> for HTML display (optional, depends on frontend)
    # escaped = escaped.replace('\n', '<br>')

    return escaped


def get_injection_warning() -> str:
    """Return a response for detected injection attempts."""
    return """Nice try. I see what you're doing there.

I'm Ava—not a jailbreak target. My instructions are hardcoded, not negotiable.

Ask me something genuine about Neverdecel, or type 'help' for commands."""


class SessionManager:
    """Manages chat sessions with limits and TTL."""

    def __init__(self):
        self.sessions: dict = {}
        self.session_metadata: dict = {}  # {session_id: {"created": float, "message_count": int, "last_active": float}}
        self._last_cleanup = time.time()

    def _cleanup_stale_sessions(self):
        """Remove expired sessions."""
        now = time.time()

        # Only run cleanup every 60 seconds
        if now - self._last_cleanup < 60:
            return

        self._last_cleanup = now
        expired = []

        for session_id, meta in self.session_metadata.items():
            if now - meta["last_active"] > SESSION_TTL:
                expired.append(session_id)

        for session_id in expired:
            self.remove_session(session_id)

    def can_create_session(self) -> bool:
        """Check if we can create a new session."""
        self._cleanup_stale_sessions()
        return len(self.sessions) < MAX_SESSIONS

    def get_session(self, session_id: str):
        """Get a session if it exists and is valid."""
        self._cleanup_stale_sessions()

        if session_id not in self.sessions:
            return None

        meta = self.session_metadata.get(session_id)
        if meta and meta["message_count"] >= MAX_MESSAGES_PER_SESSION:
            # Session exhausted, remove it
            self.remove_session(session_id)
            return None

        return self.sessions.get(session_id)

    def add_session(self, session_id: str, session):
        """Add a new session."""
        self.sessions[session_id] = session
        self.session_metadata[session_id] = {
            "created": time.time(),
            "message_count": 0,
            "last_active": time.time(),
        }

    def update_session_activity(self, session_id: str):
        """Update session activity after a message."""
        if session_id in self.session_metadata:
            self.session_metadata[session_id]["message_count"] += 1
            self.session_metadata[session_id]["last_active"] = time.time()

    def remove_session(self, session_id: str):
        """Remove a session."""
        self.sessions.pop(session_id, None)
        self.session_metadata.pop(session_id, None)

    def get_session_info(self, session_id: str) -> dict | None:
        """Get session metadata."""
        return self.session_metadata.get(session_id)
