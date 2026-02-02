"""SQLite storage for analytics data."""

import contextlib
import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class AnalyticsStorage:
    """Thread-safe SQLite storage for analytics."""

    def __init__(self, db_path: str | Path = "data/analytics.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=10.0,
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pageviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                path TEXT NOT NULL,
                referrer TEXT,
                referrer_domain TEXT,
                visitor_id TEXT NOT NULL,
                country TEXT,
                city TEXT,
                user_agent TEXT,
                browser TEXT,
                browser_version TEXT,
                os TEXT,
                device_type TEXT,
                is_bot INTEGER DEFAULT 0,
                response_time_ms INTEGER,
                status_code INTEGER,
                utm_source TEXT,
                utm_medium TEXT,
                utm_campaign TEXT,
                utm_content TEXT,
                utm_term TEXT
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_name TEXT NOT NULL,
                visitor_id TEXT NOT NULL,
                path TEXT,
                metadata TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                pageviews INTEGER DEFAULT 1,
                entry_path TEXT,
                exit_path TEXT,
                referrer TEXT,
                country TEXT,
                device_type TEXT
            );

            CREATE TABLE IF NOT EXISTS admin_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                success INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip_address);

            CREATE INDEX IF NOT EXISTS idx_pageviews_timestamp ON pageviews(timestamp);
            CREATE INDEX IF NOT EXISTS idx_pageviews_path ON pageviews(path);
            CREATE INDEX IF NOT EXISTS idx_pageviews_visitor ON pageviews(visitor_id);
            CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_events_name ON events(event_name);
            CREATE INDEX IF NOT EXISTS idx_sessions_visitor ON sessions(visitor_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);
            CREATE INDEX IF NOT EXISTS idx_admin_sessions_id ON admin_sessions(session_id);
        """)
        conn.commit()

    def record_pageview(
        self,
        path: str,
        visitor_id: str,
        referrer: str | None = None,
        referrer_domain: str | None = None,
        country: str | None = None,
        city: str | None = None,
        user_agent: str | None = None,
        browser: str | None = None,
        browser_version: str | None = None,
        os: str | None = None,
        device_type: str | None = None,
        is_bot: bool = False,
        response_time_ms: int | None = None,
        status_code: int | None = None,
        utm_source: str | None = None,
        utm_medium: str | None = None,
        utm_campaign: str | None = None,
        utm_content: str | None = None,
        utm_term: str | None = None,
    ) -> int:
        """Record a pageview and update session."""
        conn = self._get_conn()
        timestamp = datetime.utcnow().isoformat()

        cursor = conn.execute(
            """
            INSERT INTO pageviews (
                timestamp, path, referrer, referrer_domain, visitor_id,
                country, city, user_agent, browser, browser_version,
                os, device_type, is_bot, response_time_ms, status_code,
                utm_source, utm_medium, utm_campaign, utm_content, utm_term
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                path,
                referrer,
                referrer_domain,
                visitor_id,
                country,
                city,
                user_agent,
                browser,
                browser_version,
                os,
                device_type,
                int(is_bot),
                response_time_ms,
                status_code,
                utm_source,
                utm_medium,
                utm_campaign,
                utm_content,
                utm_term,
            ),
        )
        conn.commit()

        # Update or create session (30 min window)
        self._update_session(visitor_id, path, referrer_domain, country, device_type, timestamp)

        return cursor.lastrowid

    def _update_session(
        self,
        visitor_id: str,
        path: str,
        referrer: str | None,
        country: str | None,
        device_type: str | None,
        timestamp: str,
    ) -> None:
        """Update existing session or create new one."""
        conn = self._get_conn()
        cutoff = (datetime.utcnow() - timedelta(minutes=30)).isoformat()

        # Check for existing active session
        row = conn.execute(
            """
            SELECT id, pageviews FROM sessions
            WHERE visitor_id = ? AND last_seen_at > ?
            ORDER BY last_seen_at DESC LIMIT 1
            """,
            (visitor_id, cutoff),
        ).fetchone()

        if row:
            # Update existing session
            conn.execute(
                """
                UPDATE sessions
                SET last_seen_at = ?, pageviews = ?, exit_path = ?
                WHERE id = ?
                """,
                (timestamp, row["pageviews"] + 1, path, row["id"]),
            )
        else:
            # Create new session
            conn.execute(
                """
                INSERT INTO sessions (
                    visitor_id, started_at, last_seen_at, pageviews,
                    entry_path, exit_path, referrer, country, device_type
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
                """,
                (visitor_id, timestamp, timestamp, path, path, referrer, country, device_type),
            )
        conn.commit()

    def record_event(
        self,
        event_name: str,
        visitor_id: str,
        path: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Record a custom event."""
        conn = self._get_conn()
        timestamp = datetime.utcnow().isoformat()

        metadata_json = json.dumps(metadata) if metadata else None

        cursor = conn.execute(
            """
            INSERT INTO events (timestamp, event_name, visitor_id, path, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (timestamp, event_name, visitor_id, path, metadata_json),
        )
        conn.commit()
        return cursor.lastrowid

    def get_stats(self, days: int = 30) -> dict[str, Any]:
        """Get analytics statistics for the dashboard."""
        conn = self._get_conn()
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        stats = {}

        # Total pageviews
        row = conn.execute(
            "SELECT COUNT(*) as count FROM pageviews WHERE timestamp > ? AND is_bot = 0",
            (cutoff,),
        ).fetchone()
        stats["total_pageviews"] = row["count"]

        # Unique visitors
        row = conn.execute(
            "SELECT COUNT(DISTINCT visitor_id) as count FROM pageviews WHERE timestamp > ? AND is_bot = 0",
            (cutoff,),
        ).fetchone()
        stats["unique_visitors"] = row["count"]

        # Total sessions
        row = conn.execute(
            "SELECT COUNT(*) as count FROM sessions WHERE started_at > ?",
            (cutoff,),
        ).fetchone()
        stats["total_sessions"] = row["count"]

        # Avg pageviews per session
        row = conn.execute(
            "SELECT AVG(pageviews) as avg FROM sessions WHERE started_at > ?",
            (cutoff,),
        ).fetchone()
        stats["avg_pages_per_session"] = round(row["avg"] or 0, 1)

        # Top pages
        rows = conn.execute(
            """
            SELECT path, COUNT(*) as views
            FROM pageviews WHERE timestamp > ? AND is_bot = 0
            GROUP BY path ORDER BY views DESC LIMIT 10
            """,
            (cutoff,),
        ).fetchall()
        stats["top_pages"] = [{"path": r["path"], "views": r["views"]} for r in rows]

        # Top referrer domains
        rows = conn.execute(
            """
            SELECT referrer_domain, COUNT(*) as count
            FROM pageviews
            WHERE timestamp > ? AND referrer_domain IS NOT NULL AND referrer_domain != '' AND is_bot = 0
            GROUP BY referrer_domain ORDER BY count DESC LIMIT 10
            """,
            (cutoff,),
        ).fetchall()
        stats["top_referrers"] = [
            {"referrer": r["referrer_domain"], "count": r["count"]} for r in rows
        ]

        # Full referrer URLs (for detailed view)
        rows = conn.execute(
            """
            SELECT referrer, COUNT(*) as count
            FROM pageviews
            WHERE timestamp > ? AND referrer IS NOT NULL AND referrer != '' AND is_bot = 0
            GROUP BY referrer ORDER BY count DESC LIMIT 20
            """,
            (cutoff,),
        ).fetchall()
        stats["referrer_urls"] = [{"url": r["referrer"], "count": r["count"]} for r in rows]

        # Browsers
        rows = conn.execute(
            """
            SELECT browser, COUNT(*) as count
            FROM pageviews WHERE timestamp > ? AND browser IS NOT NULL AND is_bot = 0
            GROUP BY browser ORDER BY count DESC LIMIT 10
            """,
            (cutoff,),
        ).fetchall()
        stats["browsers"] = [{"browser": r["browser"], "count": r["count"]} for r in rows]

        # Operating systems
        rows = conn.execute(
            """
            SELECT os, COUNT(*) as count
            FROM pageviews WHERE timestamp > ? AND os IS NOT NULL AND is_bot = 0
            GROUP BY os ORDER BY count DESC LIMIT 10
            """,
            (cutoff,),
        ).fetchall()
        stats["operating_systems"] = [{"os": r["os"], "count": r["count"]} for r in rows]

        # Device types
        rows = conn.execute(
            """
            SELECT device_type, COUNT(*) as count
            FROM pageviews WHERE timestamp > ? AND device_type IS NOT NULL AND is_bot = 0
            GROUP BY device_type ORDER BY count DESC
            """,
            (cutoff,),
        ).fetchall()
        stats["device_types"] = [{"device": r["device_type"], "count": r["count"]} for r in rows]

        # Countries
        rows = conn.execute(
            """
            SELECT country, COUNT(*) as count
            FROM pageviews WHERE timestamp > ? AND country IS NOT NULL AND is_bot = 0
            GROUP BY country ORDER BY count DESC LIMIT 15
            """,
            (cutoff,),
        ).fetchall()
        stats["countries"] = [{"country": r["country"], "count": r["count"]} for r in rows]

        # Cities (top 10)
        rows = conn.execute(
            """
            SELECT city, country, COUNT(*) as count
            FROM pageviews WHERE timestamp > ? AND city IS NOT NULL AND is_bot = 0
            GROUP BY city, country ORDER BY count DESC LIMIT 10
            """,
            (cutoff,),
        ).fetchall()
        stats["cities"] = [
            {"city": r["city"], "country": r["country"], "count": r["count"]} for r in rows
        ]

        # Pageviews over time (daily)
        rows = conn.execute(
            """
            SELECT DATE(timestamp) as date, COUNT(*) as views
            FROM pageviews WHERE timestamp > ? AND is_bot = 0
            GROUP BY DATE(timestamp) ORDER BY date
            """,
            (cutoff,),
        ).fetchall()
        stats["pageviews_over_time"] = [{"date": r["date"], "views": r["views"]} for r in rows]

        # Visitors over time (daily unique)
        rows = conn.execute(
            """
            SELECT DATE(timestamp) as date, COUNT(DISTINCT visitor_id) as visitors
            FROM pageviews WHERE timestamp > ? AND is_bot = 0
            GROUP BY DATE(timestamp) ORDER BY date
            """,
            (cutoff,),
        ).fetchall()
        stats["visitors_over_time"] = [{"date": r["date"], "visitors": r["visitors"]} for r in rows]

        # Events summary
        rows = conn.execute(
            """
            SELECT event_name, COUNT(*) as count
            FROM events WHERE timestamp > ?
            GROUP BY event_name ORDER BY count DESC LIMIT 20
            """,
            (cutoff,),
        ).fetchall()
        stats["events"] = [{"event": r["event_name"], "count": r["count"]} for r in rows]

        # UTM sources
        rows = conn.execute(
            """
            SELECT utm_source, COUNT(*) as count
            FROM pageviews
            WHERE timestamp > ? AND utm_source IS NOT NULL AND is_bot = 0
            GROUP BY utm_source ORDER BY count DESC LIMIT 10
            """,
            (cutoff,),
        ).fetchall()
        stats["utm_sources"] = [{"source": r["utm_source"], "count": r["count"]} for r in rows]

        # UTM campaigns
        rows = conn.execute(
            """
            SELECT utm_campaign, utm_source, COUNT(*) as count
            FROM pageviews
            WHERE timestamp > ? AND utm_campaign IS NOT NULL AND is_bot = 0
            GROUP BY utm_campaign, utm_source ORDER BY count DESC LIMIT 10
            """,
            (cutoff,),
        ).fetchall()
        stats["utm_campaigns"] = [
            {"campaign": r["utm_campaign"], "source": r["utm_source"], "count": r["count"]}
            for r in rows
        ]

        # Bot traffic
        row = conn.execute(
            "SELECT COUNT(*) as count FROM pageviews WHERE timestamp > ? AND is_bot = 1",
            (cutoff,),
        ).fetchone()
        stats["bot_requests"] = row["count"]

        # Live visitors (last 5 minutes)
        live_cutoff = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
        row = conn.execute(
            "SELECT COUNT(DISTINCT visitor_id) as count FROM pageviews WHERE timestamp > ? AND is_bot = 0",
            (live_cutoff,),
        ).fetchone()
        stats["live_visitors"] = row["count"]

        return stats

    def get_recent_visitors(self, limit: int = 50) -> list[dict]:
        """Get recent visitor activity."""
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT timestamp, path, visitor_id, country, city, browser, os, device_type, referrer
            FROM pageviews
            WHERE is_bot = 0
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_visitors(self, days: int = 30) -> list[dict]:
        """Get all unique visitors with summary stats."""
        conn = self._get_conn()
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        rows = conn.execute(
            """
            SELECT
                visitor_id,
                MIN(timestamp) as first_seen,
                MAX(timestamp) as last_seen,
                COUNT(*) as pageviews,
                COUNT(DISTINCT path) as unique_pages,
                MAX(country) as country,
                MAX(city) as city,
                MAX(browser) as browser,
                MAX(os) as os,
                MAX(device_type) as device_type,
                MAX(referrer) as referrer,
                MAX(utm_source) as utm_source
            FROM pageviews
            WHERE timestamp > ? AND is_bot = 0
            GROUP BY visitor_id
            ORDER BY last_seen DESC
            """,
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_visitor_details(self, visitor_id: str) -> dict:
        """Get detailed information about a specific visitor."""

        conn = self._get_conn()

        # Get all pageviews
        pageviews = conn.execute(
            """
            SELECT timestamp, path, referrer, country, city, browser, os,
                   device_type, utm_source, utm_medium, utm_campaign, response_time_ms
            FROM pageviews
            WHERE visitor_id = ? AND is_bot = 0
            ORDER BY timestamp DESC
            """,
            (visitor_id,),
        ).fetchall()

        # Get all events
        events = conn.execute(
            """
            SELECT timestamp, event_name, path, metadata
            FROM events
            WHERE visitor_id = ?
            ORDER BY timestamp DESC
            """,
            (visitor_id,),
        ).fetchall()

        # Get sessions
        sessions = conn.execute(
            """
            SELECT started_at, last_seen_at, pageviews, entry_path, exit_path, referrer
            FROM sessions
            WHERE visitor_id = ?
            ORDER BY started_at DESC
            """,
            (visitor_id,),
        ).fetchall()

        # Parse event metadata
        parsed_events = []
        for e in events:
            event = dict(e)
            if event.get("metadata"):
                with contextlib.suppress(json.JSONDecodeError):
                    event["metadata"] = json.loads(event["metadata"])
            parsed_events.append(event)

        # Calculate summary
        if pageviews:
            first_pv = pageviews[-1]
            last_pv = pageviews[0]
            summary = {
                "visitor_id": visitor_id,
                "first_seen": first_pv["timestamp"],
                "last_seen": last_pv["timestamp"],
                "total_pageviews": len(pageviews),
                "total_events": len(events),
                "total_sessions": len(sessions),
                "country": last_pv["country"],
                "city": last_pv["city"],
                "browser": last_pv["browser"],
                "os": last_pv["os"],
                "device_type": last_pv["device_type"],
                "initial_referrer": first_pv["referrer"],
                "utm_source": first_pv["utm_source"],
                "utm_medium": first_pv["utm_medium"],
                "utm_campaign": first_pv["utm_campaign"],
            }
        else:
            summary = {"visitor_id": visitor_id}

        return {
            "summary": summary,
            "pageviews": [dict(p) for p in pageviews],
            "events": parsed_events,
            "sessions": [dict(s) for s in sessions],
        }

    def get_event_details(self, event_name: str, days: int = 30, limit: int = 50) -> list[dict]:
        """Get detailed event data with metadata."""

        conn = self._get_conn()
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        rows = conn.execute(
            """
            SELECT timestamp, event_name, path, metadata
            FROM events
            WHERE event_name = ? AND timestamp > ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (event_name, cutoff, limit),
        ).fetchall()

        results = []
        for r in rows:
            item = dict(r)
            if item.get("metadata"):
                item["metadata"] = json.loads(item["metadata"])
            results.append(item)
        return results

    def get_tile_clicks(self, days: int = 30) -> list[dict]:
        """Get project/tile click statistics."""

        conn = self._get_conn()
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        rows = conn.execute(
            """
            SELECT metadata, COUNT(*) as count
            FROM events
            WHERE event_name = 'tile_click' AND timestamp > ?
            GROUP BY metadata
            ORDER BY count DESC
            """,
            (cutoff,),
        ).fetchall()

        results = []
        for r in rows:
            if r["metadata"]:
                meta = json.loads(r["metadata"])
                results.append(
                    {
                        "project": meta.get("project", "unknown"),
                        "count": r["count"],
                    }
                )
        return results

    def get_outbound_clicks(self, days: int = 30) -> list[dict]:
        """Get outbound link click statistics."""

        conn = self._get_conn()
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        rows = conn.execute(
            """
            SELECT metadata, COUNT(*) as count
            FROM events
            WHERE event_name = 'outbound_click' AND timestamp > ?
            GROUP BY metadata
            ORDER BY count DESC
            """,
            (cutoff,),
        ).fetchall()

        results = []
        for r in rows:
            if r["metadata"]:
                meta = json.loads(r["metadata"])
                results.append(
                    {
                        "url": meta.get("url", "unknown"),
                        "text": meta.get("text", ""),
                        "count": r["count"],
                    }
                )
        return results

    # Admin session management

    def create_admin_session(self, session_id: str, expires_hours: int = 24) -> None:
        """Create a new admin session."""
        conn = self._get_conn()
        now = datetime.utcnow()
        expires = now + timedelta(hours=expires_hours)

        conn.execute(
            """
            INSERT INTO admin_sessions (session_id, created_at, expires_at)
            VALUES (?, ?, ?)
            """,
            (session_id, now.isoformat(), expires.isoformat()),
        )
        conn.commit()

        # Clean up expired sessions
        self._cleanup_expired_sessions()

    def validate_admin_session(self, session_id: str) -> bool:
        """Check if an admin session is valid."""
        if not session_id:
            return False

        conn = self._get_conn()
        now = datetime.utcnow().isoformat()

        row = conn.execute(
            """
            SELECT 1 FROM admin_sessions
            WHERE session_id = ? AND expires_at > ?
            """,
            (session_id, now),
        ).fetchone()

        return row is not None

    def delete_admin_session(self, session_id: str) -> None:
        """Delete an admin session."""
        conn = self._get_conn()
        conn.execute("DELETE FROM admin_sessions WHERE session_id = ?", (session_id,))
        conn.commit()

    def _cleanup_expired_sessions(self) -> None:
        """Remove expired admin sessions."""
        conn = self._get_conn()
        now = datetime.utcnow().isoformat()
        conn.execute("DELETE FROM admin_sessions WHERE expires_at < ?", (now,))
        conn.commit()

    # Brute force protection

    def record_login_attempt(self, ip_address: str, success: bool) -> None:
        """Record a login attempt."""
        conn = self._get_conn()
        timestamp = datetime.utcnow().isoformat()

        conn.execute(
            "INSERT INTO login_attempts (ip_address, timestamp, success) VALUES (?, ?, ?)",
            (ip_address, timestamp, int(success)),
        )
        conn.commit()

        # Clean up old attempts (older than 24 hours)
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        conn.execute("DELETE FROM login_attempts WHERE timestamp < ?", (cutoff,))
        conn.commit()

    def is_ip_locked_out(
        self, ip_address: str, max_attempts: int = 5, lockout_minutes: int = 15
    ) -> tuple[bool, int]:
        """
        Check if an IP is locked out due to too many failed attempts.
        Returns (is_locked, seconds_remaining).
        """
        conn = self._get_conn()
        cutoff = (datetime.utcnow() - timedelta(minutes=lockout_minutes)).isoformat()

        # Count failed attempts in the lockout window
        row = conn.execute(
            """
            SELECT COUNT(*) as count, MAX(timestamp) as last_attempt
            FROM login_attempts
            WHERE ip_address = ? AND timestamp > ? AND success = 0
            """,
            (ip_address, cutoff),
        ).fetchone()

        failed_count = row["count"]

        if failed_count >= max_attempts:
            # Calculate remaining lockout time
            last_attempt = datetime.fromisoformat(row["last_attempt"])
            unlock_time = last_attempt + timedelta(minutes=lockout_minutes)
            remaining = (unlock_time - datetime.utcnow()).total_seconds()
            return True, max(0, int(remaining))

        return False, 0

    def get_remaining_attempts(
        self, ip_address: str, max_attempts: int = 5, lockout_minutes: int = 15
    ) -> int:
        """Get the number of remaining login attempts before lockout."""
        conn = self._get_conn()
        cutoff = (datetime.utcnow() - timedelta(minutes=lockout_minutes)).isoformat()

        row = conn.execute(
            """
            SELECT COUNT(*) as count
            FROM login_attempts
            WHERE ip_address = ? AND timestamp > ? AND success = 0
            """,
            (ip_address, cutoff),
        ).fetchone()

        return max(0, max_attempts - row["count"])
