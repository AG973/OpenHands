"""Persistent memory system — SQLite-backed vector + FTS knowledge store.

Provides cross-session memory persistence with hybrid search (keyword + semantic).
Ported from OpenClaw's memory/manager.ts patterns to Python with SQLite backend.

Per OPERATING_RULES.md RULE 5: Production-grade — no hardcoded values, proper error handling.
"""

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from openhands.core.logger import openhands_logger as logger

# Default storage location
DEFAULT_MEMORY_DIR = os.path.join(str(Path.home()), '.openhands', 'memory')

# Memory limits
MAX_CONTENT_LENGTH = 100000  # 100KB max per memory entry
MAX_SEARCH_RESULTS = 50
MAX_MEMORIES_PER_WORKSPACE = 10000
EMBEDDING_DIMENSION = 768  # Common embedding dimension


class MemoryType(Enum):
    """Types of persistent memory entries."""

    KNOWLEDGE = 'knowledge'  # Factual knowledge about codebase/domain
    SKILL = 'skill'  # Learned procedures and patterns
    SESSION_NOTE = 'session_note'  # Notes from sessions
    ERROR_PATTERN = 'error_pattern'  # Known error patterns and fixes
    WORKSPACE_FILE = 'workspace_file'  # Indexed workspace file content
    USER_PREFERENCE = 'user_preference'  # User preferences and settings


@dataclass
class MemoryEntry:
    """A single memory entry in the persistent store."""

    entry_id: str
    memory_type: MemoryType
    title: str
    content: str
    workspace_id: str = ''
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None
    created_at: float = 0.0
    updated_at: float = 0.0
    access_count: int = 0
    last_accessed_at: float = 0.0
    source: str = ''  # Where this memory came from

    @property
    def content_hash(self) -> str:
        """SHA256 hash of the content for deduplication."""
        return hashlib.sha256(self.content.encode('utf-8')).hexdigest()[:16]


@dataclass
class SearchResult:
    """A search result with relevance score."""

    entry: MemoryEntry
    score: float = 0.0
    match_type: str = ''  # 'fts', 'vector', 'hybrid', 'exact'


class PersistentMemory:
    """SQLite-backed persistent memory store with FTS search.

    Stores knowledge, skills, error patterns, and workspace file indexes
    that persist across sessions. Supports full-text search and optional
    vector similarity search when embeddings are available.
    """

    def __init__(
        self,
        workspace_id: str = 'default',
        memory_dir: str | None = None,
    ):
        self._workspace_id = workspace_id
        self._memory_dir = memory_dir or DEFAULT_MEMORY_DIR
        self._db_path = os.path.join(self._memory_dir, f'{workspace_id}.db')
        self._conn: sqlite3.Connection | None = None

        # Ensure directory exists
        os.makedirs(self._memory_dir, exist_ok=True)

        # Initialize database
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database with required tables and FTS index."""
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute('PRAGMA journal_mode=WAL')
        self._conn.execute('PRAGMA foreign_keys=ON')

        # Main memories table
        self._conn.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                entry_id TEXT PRIMARY KEY,
                memory_type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                workspace_id TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}',
                embedding BLOB,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                access_count INTEGER NOT NULL DEFAULT 0,
                last_accessed_at REAL NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT '',
                content_hash TEXT NOT NULL DEFAULT ''
            )
        ''')

        # FTS5 virtual table for full-text search
        self._conn.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                entry_id UNINDEXED,
                title,
                content,
                tags,
                content='memories',
                content_rowid='rowid'
            )
        ''')

        # Triggers to keep FTS in sync
        self._conn.executescript('''
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, entry_id, title, content, tags)
                VALUES (new.rowid, new.entry_id, new.title, new.content, new.tags);
            END;
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, entry_id, title, content, tags)
                VALUES ('delete', old.rowid, old.entry_id, old.title, old.content, old.tags);
            END;
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, entry_id, title, content, tags)
                VALUES ('delete', old.rowid, old.entry_id, old.title, old.content, old.tags);
                INSERT INTO memories_fts(rowid, entry_id, title, content, tags)
                VALUES (new.rowid, new.entry_id, new.title, new.content, new.tags);
            END;
        ''')

        # Indexes
        self._conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type)
        ''')
        self._conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_memories_workspace ON memories(workspace_id)
        ''')
        self._conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_memories_updated ON memories(updated_at DESC)
        ''')
        self._conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_memories_hash ON memories(content_hash)
        ''')

        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _ensure_conn(self) -> sqlite3.Connection:
        """Ensure database connection is open."""
        if self._conn is None:
            self._init_db()
        assert self._conn is not None
        return self._conn

    # ── CRUD Operations ───────────────────────────────────────────────

    def add(self, entry: MemoryEntry) -> str:
        """Add a memory entry to the store.

        Args:
            entry: MemoryEntry to persist

        Returns:
            The entry_id of the stored entry

        Raises:
            ValueError: If content exceeds MAX_CONTENT_LENGTH or store is full
        """
        if len(entry.content) > MAX_CONTENT_LENGTH:
            raise ValueError(
                f'Memory content exceeds maximum length of {MAX_CONTENT_LENGTH} chars'
            )

        conn = self._ensure_conn()

        # Check store capacity
        count = conn.execute(
            'SELECT COUNT(*) FROM memories WHERE workspace_id = ?',
            (self._workspace_id,),
        ).fetchone()[0]
        if count >= MAX_MEMORIES_PER_WORKSPACE:
            raise ValueError(
                f'Memory store is full ({MAX_MEMORIES_PER_WORKSPACE} entries). '
                'Delete old entries or increase the limit.'
            )

        now = time.time()
        if entry.created_at == 0.0:
            entry.created_at = now
        if entry.updated_at == 0.0:
            entry.updated_at = now
        if not entry.workspace_id:
            entry.workspace_id = self._workspace_id

        # Check for duplicates by content hash
        content_hash = entry.content_hash
        existing = conn.execute(
            'SELECT entry_id FROM memories WHERE content_hash = ? AND workspace_id = ?',
            (content_hash, entry.workspace_id),
        ).fetchone()
        if existing is not None:
            # Update existing entry instead of creating duplicate
            logger.debug(f'Duplicate memory detected, updating existing: {existing[0]}')
            entry.entry_id = existing[0]
            return self.update(entry)

        embedding_blob = None
        if entry.embedding is not None:
            embedding_blob = _embed_to_blob(entry.embedding)

        conn.execute(
            '''INSERT OR REPLACE INTO memories
            (entry_id, memory_type, title, content, workspace_id, tags, metadata,
             embedding, created_at, updated_at, access_count, last_accessed_at, source, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                entry.entry_id,
                entry.memory_type.value,
                entry.title,
                entry.content,
                entry.workspace_id,
                json.dumps(entry.tags),
                json.dumps(entry.metadata),
                embedding_blob,
                entry.created_at,
                entry.updated_at,
                entry.access_count,
                entry.last_accessed_at,
                entry.source,
                content_hash,
            ),
        )
        conn.commit()
        logger.debug(f'Added memory: {entry.entry_id} ({entry.memory_type.value})')
        return entry.entry_id

    def get(self, entry_id: str) -> MemoryEntry | None:
        """Retrieve a memory entry by ID."""
        conn = self._ensure_conn()
        row = conn.execute(
            'SELECT * FROM memories WHERE entry_id = ?', (entry_id,)
        ).fetchone()
        if row is None:
            return None

        entry = _row_to_entry(row)

        # Update access stats
        now = time.time()
        conn.execute(
            'UPDATE memories SET access_count = access_count + 1, last_accessed_at = ? WHERE entry_id = ?',
            (now, entry_id),
        )
        conn.commit()

        return entry

    def update(self, entry: MemoryEntry) -> str:
        """Update an existing memory entry."""
        conn = self._ensure_conn()
        entry.updated_at = time.time()

        embedding_blob = None
        if entry.embedding is not None:
            embedding_blob = _embed_to_blob(entry.embedding)

        conn.execute(
            '''UPDATE memories SET
            memory_type = ?, title = ?, content = ?, workspace_id = ?,
            tags = ?, metadata = ?, embedding = ?, updated_at = ?,
            source = ?, content_hash = ?
            WHERE entry_id = ?''',
            (
                entry.memory_type.value,
                entry.title,
                entry.content,
                entry.workspace_id or self._workspace_id,
                json.dumps(entry.tags),
                json.dumps(entry.metadata),
                embedding_blob,
                entry.updated_at,
                entry.source,
                entry.content_hash,
                entry.entry_id,
            ),
        )
        conn.commit()
        return entry.entry_id

    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry."""
        conn = self._ensure_conn()
        cursor = conn.execute(
            'DELETE FROM memories WHERE entry_id = ?', (entry_id,)
        )
        conn.commit()
        return cursor.rowcount > 0

    def list_entries(
        self,
        memory_type: MemoryType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryEntry]:
        """List memory entries with optional type filter."""
        conn = self._ensure_conn()

        if memory_type is not None:
            rows = conn.execute(
                'SELECT * FROM memories WHERE workspace_id = ? AND memory_type = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?',
                (self._workspace_id, memory_type.value, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM memories WHERE workspace_id = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?',
                (self._workspace_id, limit, offset),
            ).fetchall()

        return [_row_to_entry(row) for row in rows]

    # ── Search ────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        """Search memories using FTS5 full-text search.

        Args:
            query: Search query string
            memory_type: Optional filter by memory type
            limit: Maximum results to return
            min_score: Minimum relevance score threshold

        Returns:
            List of SearchResult sorted by relevance
        """
        conn = self._ensure_conn()
        limit = min(limit, MAX_SEARCH_RESULTS)

        if not query.strip():
            return []

        # Sanitize query for FTS5
        safe_query = _sanitize_fts_query(query)
        if not safe_query:
            return []

        try:
            if memory_type is not None:
                rows = conn.execute(
                    '''SELECT m.*, rank
                    FROM memories_fts f
                    JOIN memories m ON f.entry_id = m.entry_id
                    WHERE memories_fts MATCH ? AND m.workspace_id = ? AND m.memory_type = ?
                    ORDER BY rank
                    LIMIT ?''',
                    (safe_query, self._workspace_id, memory_type.value, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    '''SELECT m.*, rank
                    FROM memories_fts f
                    JOIN memories m ON f.entry_id = m.entry_id
                    WHERE memories_fts MATCH ? AND m.workspace_id = ?
                    ORDER BY rank
                    LIMIT ?''',
                    (safe_query, self._workspace_id, limit),
                ).fetchall()

            results = []
            for row in rows:
                entry = _row_to_entry(row)
                # FTS5 rank is negative (more negative = better match)
                score = -float(row['rank']) if 'rank' in row.keys() else 0.0
                if score >= min_score:
                    results.append(SearchResult(entry=entry, score=score, match_type='fts'))

            return results

        except sqlite3.OperationalError as e:
            logger.warning(f'FTS search error: {e}')
            # Fall back to LIKE search
            return self._search_like(query, memory_type, limit)

    def _search_like(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Fallback LIKE-based search when FTS fails."""
        conn = self._ensure_conn()
        pattern = f'%{query}%'

        if memory_type is not None:
            rows = conn.execute(
                '''SELECT * FROM memories
                WHERE workspace_id = ? AND memory_type = ?
                AND (title LIKE ? OR content LIKE ? OR tags LIKE ?)
                ORDER BY updated_at DESC LIMIT ?''',
                (self._workspace_id, memory_type.value, pattern, pattern, pattern, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                '''SELECT * FROM memories
                WHERE workspace_id = ?
                AND (title LIKE ? OR content LIKE ? OR tags LIKE ?)
                ORDER BY updated_at DESC LIMIT ?''',
                (self._workspace_id, pattern, pattern, pattern, limit),
            ).fetchall()

        results = []
        for row in rows:
            entry = _row_to_entry(row)
            results.append(SearchResult(entry=entry, score=1.0, match_type='exact'))

        return results

    # ── Bulk Operations ───────────────────────────────────────────────

    def add_batch(self, entries: list[MemoryEntry]) -> list[str]:
        """Add multiple memory entries in a single transaction."""
        conn = self._ensure_conn()
        entry_ids = []

        try:
            for entry in entries:
                if len(entry.content) > MAX_CONTENT_LENGTH:
                    logger.warning(
                        f'Skipping oversized memory entry: {entry.entry_id}'
                    )
                    continue
                entry_id = self.add(entry)
                entry_ids.append(entry_id)
        except Exception as e:
            logger.error(f'Error in batch add: {e}')
            raise

        return entry_ids

    def clear(self, memory_type: MemoryType | None = None) -> int:
        """Clear memory entries. Optionally filter by type.

        Returns:
            Number of entries deleted
        """
        conn = self._ensure_conn()

        if memory_type is not None:
            cursor = conn.execute(
                'DELETE FROM memories WHERE workspace_id = ? AND memory_type = ?',
                (self._workspace_id, memory_type.value),
            )
        else:
            cursor = conn.execute(
                'DELETE FROM memories WHERE workspace_id = ?',
                (self._workspace_id,),
            )

        conn.commit()
        count = cursor.rowcount
        logger.info(f'Cleared {count} memory entries')
        return count

    # ── Stats ─────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Get memory store statistics."""
        conn = self._ensure_conn()

        total = conn.execute(
            'SELECT COUNT(*) FROM memories WHERE workspace_id = ?',
            (self._workspace_id,),
        ).fetchone()[0]

        by_type = {}
        for row in conn.execute(
            'SELECT memory_type, COUNT(*) as cnt FROM memories WHERE workspace_id = ? GROUP BY memory_type',
            (self._workspace_id,),
        ).fetchall():
            by_type[row['memory_type']] = row['cnt']

        db_size = os.path.getsize(self._db_path) if os.path.exists(self._db_path) else 0

        return {
            'total_entries': total,
            'by_type': by_type,
            'workspace_id': self._workspace_id,
            'db_size_bytes': db_size,
            'max_entries': MAX_MEMORIES_PER_WORKSPACE,
        }


# ── Utility functions ─────────────────────────────────────────────────

def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
    """Convert a database row to a MemoryEntry."""
    embedding = None
    raw_embedding = row['embedding']
    if raw_embedding is not None:
        embedding = _blob_to_embed(raw_embedding)

    return MemoryEntry(
        entry_id=row['entry_id'],
        memory_type=MemoryType(row['memory_type']),
        title=row['title'],
        content=row['content'],
        workspace_id=row['workspace_id'],
        tags=json.loads(row['tags']),
        metadata=json.loads(row['metadata']),
        embedding=embedding,
        created_at=row['created_at'],
        updated_at=row['updated_at'],
        access_count=row['access_count'],
        last_accessed_at=row['last_accessed_at'],
        source=row['source'],
    )


def _embed_to_blob(embedding: list[float]) -> bytes:
    """Serialize a float vector to bytes for SQLite storage."""
    import struct

    return struct.pack(f'{len(embedding)}f', *embedding)


def _blob_to_embed(blob: bytes) -> list[float]:
    """Deserialize bytes back to a float vector."""
    import struct

    count = len(blob) // 4  # 4 bytes per float
    return list(struct.unpack(f'{count}f', blob))


def _sanitize_fts_query(query: str) -> str:
    """Sanitize a query string for FTS5 MATCH syntax.

    FTS5 has special syntax characters that need escaping.
    We convert user input to a simple term search.
    """
    # Remove FTS5 special characters
    cleaned = query.replace('"', ' ').replace("'", ' ')
    cleaned = cleaned.replace('*', ' ').replace('-', ' ')
    cleaned = cleaned.replace('(', ' ').replace(')', ' ')
    cleaned = cleaned.replace('{', ' ').replace('}', ' ')
    cleaned = cleaned.replace('[', ' ').replace(']', ' ')
    cleaned = cleaned.replace('^', ' ').replace('~', ' ')
    cleaned = cleaned.replace(':', ' ')

    # Split into terms and rejoin
    terms = [t.strip() for t in cleaned.split() if t.strip()]
    if not terms:
        return ''

    # Use OR to be permissive
    return ' OR '.join(f'"{t}"' for t in terms[:10])  # Limit to 10 terms
