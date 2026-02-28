"""
Schema — the shape of memory.

Tables:
  events + event_tags   — raw log, append-only
  working_memory        — active knowledge
  fragments + edges     — compiled knowledge, three tiers
  state                 — metadata (turn counter, etc.)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_VERSION = 4


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def migrate(db_path: Path) -> None:
    """Create or update the schema. Safe to call every startup."""
    conn = connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER NOT NULL
            )
        """)
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        current = row["version"] if row else 0
        if current < 1:
            _create_v1(conn)
        if current < 2:
            _migrate_v1_to_v2(conn)
        if current < 3:
            _migrate_v2_to_v3(conn)
        if current < 4:
            _migrate_v3_to_v4(conn)
        conn.execute("DELETE FROM schema_version")
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        conn.commit()
    finally:
        conn.close()


def _create_v1(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL,
            content TEXT NOT NULL, actor TEXT, image_path TEXT);
        CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
        CREATE TABLE IF NOT EXISTS event_tags (
            event_id INTEGER NOT NULL, tag TEXT NOT NULL,
            PRIMARY KEY (event_id, tag),
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE);
        CREATE INDEX IF NOT EXISTS idx_event_tags_tag ON event_tags(tag);
        CREATE TABLE IF NOT EXISTS fragments (
            key TEXT PRIMARY KEY, ambient TEXT, recognition TEXT,
            inventory TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS fragment_sources (
            fragment_key TEXT NOT NULL, event_id INTEGER NOT NULL,
            PRIMARY KEY (fragment_key, event_id),
            FOREIGN KEY (fragment_key) REFERENCES fragments(key) ON DELETE CASCADE,
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS fragment_edges (
            source_key TEXT NOT NULL, target_key TEXT NOT NULL, relation TEXT,
            PRIMARY KEY (source_key, target_key),
            FOREIGN KEY (source_key) REFERENCES fragments(key) ON DELETE CASCADE,
            FOREIGN KEY (target_key) REFERENCES fragments(key) ON DELETE CASCADE);
        CREATE INDEX IF NOT EXISTS idx_fragment_edges_source ON fragment_edges(source_key);
        CREATE INDEX IF NOT EXISTS idx_fragment_edges_target ON fragment_edges(target_key);
        CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS maintenance_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL,
            completed_at TEXT, run_type TEXT NOT NULL);
    """)


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS working_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER,
            type TEXT NOT NULL, content TEXT NOT NULL, subject TEXT,
            actor TEXT, status TEXT NOT NULL DEFAULT 'active', due TEXT,
            turn INTEGER, created_at TEXT NOT NULL, refreshed_at TEXT NOT NULL,
            resolved_at TEXT,
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE SET NULL);
        CREATE INDEX IF NOT EXISTS idx_wm_status ON working_memory(status);
        CREATE INDEX IF NOT EXISTS idx_wm_type_status ON working_memory(type, status);
        CREATE INDEX IF NOT EXISTS idx_wm_due ON working_memory(due) WHERE due IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_wm_subject ON working_memory(subject) WHERE subject IS NOT NULL;
        CREATE TABLE IF NOT EXISTS working_memory_refs (
            wm_id INTEGER NOT NULL, fragment_key TEXT NOT NULL,
            PRIMARY KEY (wm_id, fragment_key),
            FOREIGN KEY (wm_id) REFERENCES working_memory(id) ON DELETE CASCADE,
            FOREIGN KEY (fragment_key) REFERENCES fragments(key) ON DELETE CASCADE);
    """)


def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(working_memory)")}
    if "turn" not in cols:
        conn.execute("ALTER TABLE working_memory ADD COLUMN turn INTEGER")


def _migrate_v3_to_v4(conn: sqlite3.Connection) -> None:
    """Add working_memory_deps table for WM item dependencies."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS working_memory_deps (
            wm_id        INTEGER NOT NULL,
            blocked_by   INTEGER NOT NULL,
            PRIMARY KEY (wm_id, blocked_by),
            FOREIGN KEY (wm_id) REFERENCES working_memory(id) ON DELETE CASCADE,
            FOREIGN KEY (blocked_by) REFERENCES working_memory(id) ON DELETE CASCADE
        );
    """)


VALID_WM_TYPES = frozenset({"feeling", "thought", "pattern", "desc", "plan", "pin", "secret"})
VALID_WM_STATUSES = frozenset({"active", "resolved", "dropped", "decayed", "superseded"})
DISPLAY_TAGS = frozenset({"say", "do", "narrate"})
ALL_TAGS = VALID_WM_TYPES | DISPLAY_TAGS
IDENTITY_TAGS = frozenset()
