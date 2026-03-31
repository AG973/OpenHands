"""CODEIT persistent storage — SQLite database for custom features."""

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from openhands.core.logger import openhands_logger as logger

# Default DB path: ~/.codeit/codeit.db (survives restarts, outside repo)
_DB_DIR = os.environ.get("CODEIT_DATA_DIR", os.path.expanduser("~/.codeit"))
_DB_PATH = os.path.join(_DB_DIR, "codeit.db")


def get_db_path() -> str:
    return _DB_PATH


_local = threading.local()


def _get_connection() -> sqlite3.Connection:
    """Get a thread-local SQLite connection with WAL mode for concurrent reads."""
    if not hasattr(_local, "conn") or _local.conn is None:
        Path(_DB_DIR).mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(_DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn


@contextmanager
def get_db():
    """Context manager yielding a SQLite connection. Auto-commits on success, rolls back on error."""
    conn = _get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ─── Schema Migration ──────────────────────────────────────────────────────────

_SCHEMA_VERSION = 1

_MIGRATIONS: dict[int, list[str]] = {
    1: [
        # Users table (for auth)
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            role TEXT DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",
        # Skills
        """CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            content TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",
        # Knowledge
        """CREATE TABLE IF NOT EXISTS knowledge (
            id TEXT PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",
        # Prompts
        """CREATE TABLE IF NOT EXISTS prompts (
            id TEXT PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            content TEXT DEFAULT '',
            active INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",
        # Connectors (config stored as JSON — sensitive values masked in API responses)
        """CREATE TABLE IF NOT EXISTS connectors (
            id TEXT PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            icon TEXT DEFAULT '',
            status TEXT DEFAULT 'disconnected',
            config_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",
        # Deploy jobs
        """CREATE TABLE IF NOT EXISTS deploy_jobs (
            id TEXT PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            target TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            logs TEXT DEFAULT '',
            config TEXT DEFAULT '{}',
            result TEXT DEFAULT '',
            error TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            finished_at TEXT
        )""",
        # File uploads
        """CREATE TABLE IF NOT EXISTS file_uploads (
            id TEXT PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            original_name TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            mime_type TEXT DEFAULT '',
            size_bytes INTEGER DEFAULT 0,
            conversation_id TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        )""",
        # Schema version tracker
        """CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY
        )""",
    ],
}


def init_db() -> None:
    """Run all pending migrations to bring DB up to current schema version."""
    Path(_DB_DIR).mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        # Check current version
        try:
            row = conn.execute(
                "SELECT MAX(version) as v FROM schema_version"
            ).fetchone()
            current = row["v"] if row and row["v"] else 0
        except sqlite3.OperationalError:
            current = 0

        if current >= _SCHEMA_VERSION:
            logger.info(f"CODEIT DB at version {current}, no migrations needed")
            return

        for ver in range(_SCHEMA_VERSION + 1):
            if ver <= current:
                continue
            if ver in _MIGRATIONS:
                logger.info(f"CODEIT DB: applying migration v{ver}")
                for sql in _MIGRATIONS[ver]:
                    conn.execute(sql)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (ver,)
                )

        logger.info(f"CODEIT DB initialized at version {_SCHEMA_VERSION}: {_DB_PATH}")
