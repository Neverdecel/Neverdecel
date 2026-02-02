"""SQLite storage for analytics data."""

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
                visitor_hash TEXT NOT NULL,
                ip_address TEXT,
                country TEXT,
                city TEXT,
                user_agent TEXT,
                browser TEXT,
                browser_version TEXT,
                os TEXT,
                device_type TEXT,
                is_bot INTEGER DEFAULT 0,
                response_time_ms INTEGER,
                status_code INTEGER
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_name TEXT NOT NULL,
                visitor_hash TEXT NOT NULL,
                path TEXT,
                metadata TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_hash TEXT NOT NULL,
                started_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                pageviews INTEGER DEFAULT 1,
                entry_path TEXT,
                exit_path TEXT,
                referrer TEXT,
                country TEXT,
                device_type TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_pageviews_timestamp ON pageviews(timestamp);
            CREATE INDEX IF NOT EXISTS idx_pageviews_path ON pageviews(path);
            CREATE INDEX IF NOT EXISTS idx_pageviews_visitor ON pageviews(visitor_hash);
            CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_events_name ON events(event_name);
            CREATE INDEX IF NOT EXISTS idx_sessions_visitor ON sessions(visitor_hash);
            CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);
        """)
        conn.commit()

    def record_pageview(
        self,
        path: str,
        visitor_hash: str,
        ip_address: str | None = None,
        referrer: str | None = None,
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
    ) -> int:
        """Record a pageview and update session."""
        conn = self._get_conn()
        timestamp = datetime.utcnow().isoformat()

        cursor = conn.execute(
            """
            INSERT INTO pageviews (
                timestamp, path, referrer, visitor_hash, ip_address,
                country, city, user_agent, browser, browser_version,
                os, device_type, is_bot, response_time_ms, status_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                path,
                referrer,
                visitor_hash,
                ip_address,
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
            ),
        )
        conn.commit()

        # Update or create session (30 min window)
        self._update_session(visitor_hash, path, referrer, country, device_type, timestamp)

        return cursor.lastrowid

    def _update_session(
        self,
        visitor_hash: str,
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
            WHERE visitor_hash = ? AND last_seen_at > ?
            ORDER BY last_seen_at DESC LIMIT 1
            """,
            (visitor_hash, cutoff),
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
                    visitor_hash, started_at, last_seen_at, pageviews,
                    entry_path, exit_path, referrer, country, device_type
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
                """,
                (visitor_hash, timestamp, timestamp, path, path, referrer, country, device_type),
            )
        conn.commit()

    def record_event(
        self,
        event_name: str,
        visitor_hash: str,
        path: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Record a custom event."""
        conn = self._get_conn()
        timestamp = datetime.utcnow().isoformat()

        import json

        metadata_json = json.dumps(metadata) if metadata else None

        cursor = conn.execute(
            """
            INSERT INTO events (timestamp, event_name, visitor_hash, path, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (timestamp, event_name, visitor_hash, path, metadata_json),
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
            "SELECT COUNT(DISTINCT visitor_hash) as count FROM pageviews WHERE timestamp > ? AND is_bot = 0",
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

        # Top referrers
        rows = conn.execute(
            """
            SELECT referrer, COUNT(*) as count
            FROM pageviews
            WHERE timestamp > ? AND referrer IS NOT NULL AND referrer != '' AND is_bot = 0
            GROUP BY referrer ORDER BY count DESC LIMIT 10
            """,
            (cutoff,),
        ).fetchall()
        stats["top_referrers"] = [{"referrer": r["referrer"], "count": r["count"]} for r in rows]

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
            SELECT DATE(timestamp) as date, COUNT(DISTINCT visitor_hash) as visitors
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

        # Bot traffic
        row = conn.execute(
            "SELECT COUNT(*) as count FROM pageviews WHERE timestamp > ? AND is_bot = 1",
            (cutoff,),
        ).fetchone()
        stats["bot_requests"] = row["count"]

        # Live visitors (last 5 minutes)
        live_cutoff = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
        row = conn.execute(
            "SELECT COUNT(DISTINCT visitor_hash) as count FROM pageviews WHERE timestamp > ? AND is_bot = 0",
            (live_cutoff,),
        ).fetchone()
        stats["live_visitors"] = row["count"]

        return stats

    def get_recent_visitors(self, limit: int = 50) -> list[dict]:
        """Get recent visitor activity."""
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT timestamp, path, country, city, browser, os, device_type, referrer
            FROM pageviews
            WHERE is_bot = 0
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
