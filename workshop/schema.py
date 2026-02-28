"""
Crystal schema — the shape of project knowledge.

Tables:
  crystals            — active knowledge units (summary + body, two tiers)
  crystal_legacy      — version history (chronological per crystal)
  crystal_edges       — graph index (directed and undirected)
  crystal_version_edges — temporal links between legacy versions
  crystals_fts        — full-text search on active crystals
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def migrate(db_path: Path) -> None:
    """Create or update the crystal schema. Safe to call every startup."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
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

        conn.execute("DELETE FROM schema_version")
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        conn.commit()
    finally:
        conn.close()


def _create_v1(conn: sqlite3.Connection) -> None:
    """Initial crystal schema."""

    conn.executescript("""
        -- Active crystals: the current version of each knowledge unit.
        -- If it's in this table, it's current. Period.
        CREATE TABLE IF NOT EXISTS crystals (
            key         TEXT PRIMARY KEY,
            type        TEXT NOT NULL,
            summary     TEXT NOT NULL,
            body        TEXT,
            edges       TEXT,
            reasoning   TEXT,
            created     TEXT NOT NULL,
            updated     TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_crystals_type ON crystals(type);

        -- Version history: old versions land here chronologically.
        -- Each crystal accumulates its own history naturally.
        CREATE TABLE IF NOT EXISTS crystal_legacy (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            key         TEXT NOT NULL,
            type        TEXT NOT NULL,
            summary     TEXT NOT NULL,
            body        TEXT,
            edges       TEXT,
            reasoning   TEXT,
            created     TEXT NOT NULL,
            archived    TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_legacy_key ON crystal_legacy(key);
        CREATE INDEX IF NOT EXISTS idx_legacy_archived ON crystal_legacy(archived);

        -- Edge index for graph queries.
        -- Duplicates what's in crystals.edges JSON, but queryable.
        CREATE TABLE IF NOT EXISTS crystal_edges (
            source      TEXT NOT NULL,
            target      TEXT NOT NULL,
            relation    TEXT NOT NULL,
            directed    INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (source, target, relation)
        );

        CREATE INDEX IF NOT EXISTS idx_edges_source ON crystal_edges(source);
        CREATE INDEX IF NOT EXISTS idx_edges_target ON crystal_edges(target);

        -- Cross-version edges: temporal links between legacy versions.
        -- "mirror v2 was active when heart v1 was active"
        CREATE TABLE IF NOT EXISTS crystal_version_edges (
            legacy_id           INTEGER NOT NULL,
            related_legacy_id   INTEGER NOT NULL,
            relation            TEXT NOT NULL,
            PRIMARY KEY (legacy_id, related_legacy_id, relation),
            FOREIGN KEY (legacy_id) REFERENCES crystal_legacy(id),
            FOREIGN KEY (related_legacy_id) REFERENCES crystal_legacy(id)
        );

        -- Full-text search on active crystals.
        CREATE VIRTUAL TABLE IF NOT EXISTS crystals_fts USING fts5(
            key, type, summary, body,
            content='crystals', content_rowid='rowid'
        );

        -- Sync triggers: keep FTS in sync with crystals table.
        CREATE TRIGGER IF NOT EXISTS crystals_ai AFTER INSERT ON crystals BEGIN
            INSERT INTO crystals_fts(rowid, key, type, summary, body)
            VALUES (new.rowid, new.key, new.type, new.summary, new.body);
        END;

        CREATE TRIGGER IF NOT EXISTS crystals_ad AFTER DELETE ON crystals BEGIN
            INSERT INTO crystals_fts(crystals_fts, rowid, key, type, summary, body)
            VALUES ('delete', old.rowid, old.key, old.type, old.summary, old.body);
        END;

        CREATE TRIGGER IF NOT EXISTS crystals_au AFTER UPDATE ON crystals BEGIN
            INSERT INTO crystals_fts(crystals_fts, rowid, key, type, summary, body)
            VALUES ('delete', old.rowid, old.key, old.type, old.summary, old.body);
            INSERT INTO crystals_fts(rowid, key, type, summary, body)
            VALUES (new.rowid, new.key, new.type, new.summary, new.body);
        END;
    """)


# ---------------------------------------------------------------------------
# Crystal operations
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_crystal(
    conn: sqlite3.Connection,
    key: str,
    type: str,
    summary: str,
    body: str | None = None,
    edges: list[dict] | None = None,
    reasoning: str | None = None,
) -> None:
    """Write or update a crystal. Old version automatically archived."""
    now = _now()
    edges_json = json.dumps(edges) if edges else None

    # Check if crystal exists — if so, archive it first
    existing = conn.execute(
        "SELECT * FROM crystals WHERE key = ?", (key,)
    ).fetchone()

    if existing:
        # Archive the current version
        conn.execute(
            """INSERT INTO crystal_legacy
               (key, type, summary, body, edges, reasoning, created, archived)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                existing["key"], existing["type"], existing["summary"],
                existing["body"], existing["edges"], existing["reasoning"],
                existing["created"], now,
            ),
        )

        # Update in place
        conn.execute(
            """UPDATE crystals
               SET type=?, summary=?, body=?, edges=?, reasoning=?, updated=?
               WHERE key=?""",
            (type, summary, body, edges_json, reasoning, now, key),
        )
    else:
        conn.execute(
            """INSERT INTO crystals (key, type, summary, body, edges, reasoning, created, updated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (key, type, summary, body, edges_json, reasoning, now, now),
        )

    # Sync edge index
    _sync_edges(conn, key, edges or [])


def delete_crystal(conn: sqlite3.Connection, key: str) -> None:
    """Archive and remove a crystal. Use for intentional removal, not updates."""
    existing = conn.execute(
        "SELECT * FROM crystals WHERE key = ?", (key,)
    ).fetchone()
    if not existing:
        return

    now = _now()
    conn.execute(
        """INSERT INTO crystal_legacy
           (key, type, summary, body, edges, reasoning, created, archived)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            existing["key"], existing["type"], existing["summary"],
            existing["body"], existing["edges"],
            "Intentionally removed", existing["created"], now,
        ),
    )
    conn.execute("DELETE FROM crystals WHERE key = ?", (key,))
    conn.execute("DELETE FROM crystal_edges WHERE source = ? OR target = ?", (key, key))


def read_crystal(conn: sqlite3.Connection, key: str) -> dict | None:
    """Read a crystal by exact key. Returns dict or None."""
    row = conn.execute("SELECT * FROM crystals WHERE key = ?", (key,)).fetchone()
    if not row:
        return None
    result = dict(row)
    if result.get("edges"):
        result["edges"] = json.loads(result["edges"])
    return result


def search_crystals(conn: sqlite3.Connection, query: str) -> list[dict]:
    """Full-text search across crystals. Returns matches with key, type, summary."""
    rows = conn.execute(
        """SELECT c.key, c.type, c.summary, c.updated
           FROM crystals_fts fts
           JOIN crystals c ON c.rowid = fts.rowid
           WHERE crystals_fts MATCH ?
           ORDER BY rank""",
        (query,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_crystals(
    conn: sqlite3.Connection, type: str | None = None
) -> list[dict]:
    """List all active crystals. Optionally filter by type."""
    if type:
        rows = conn.execute(
            "SELECT key, type, summary, updated FROM crystals WHERE type = ? ORDER BY key",
            (type,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT key, type, summary, updated FROM crystals ORDER BY type, key"
        ).fetchall()
    return [dict(r) for r in rows]


def get_neighbors(conn: sqlite3.Connection, key: str) -> list[dict]:
    """Get all crystals connected to a key via edges."""
    rows = conn.execute(
        """SELECT ce.source, ce.target, ce.relation, ce.directed,
                  c.key, c.type, c.summary
           FROM crystal_edges ce
           JOIN crystals c ON c.key = CASE
               WHEN ce.source = ? THEN ce.target
               ELSE ce.source
           END
           WHERE ce.source = ? OR (ce.target = ? AND ce.directed = 0)""",
        (key, key, key),
    ).fetchall()
    return [dict(r) for r in rows]


def get_legacy(conn: sqlite3.Connection, key: str) -> list[dict]:
    """Get version history for a crystal, newest first."""
    rows = conn.execute(
        """SELECT * FROM crystal_legacy
           WHERE key = ?
           ORDER BY archived DESC""",
        (key,),
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        if d.get("edges"):
            d["edges"] = json.loads(d["edges"])
        results.append(d)
    return results


def _sync_edges(
    conn: sqlite3.Connection, key: str, edges: list[dict]
) -> None:
    """Sync the crystal_edges table with a crystal's edge list."""
    # Remove old edges from this crystal
    conn.execute(
        "DELETE FROM crystal_edges WHERE source = ?", (key,)
    )
    # Also remove undirected edges where this key is the target
    conn.execute(
        "DELETE FROM crystal_edges WHERE target = ? AND directed = 0", (key,)
    )

    # Insert new edges
    for edge in edges:
        target = edge.get("key") or edge.get("target")
        relation = edge.get("relation", "relates-to")
        directed = 1 if edge.get("directed", True) else 0
        if target:
            conn.execute(
                """INSERT OR REPLACE INTO crystal_edges
                   (source, target, relation, directed)
                   VALUES (?, ?, ?, ?)""",
                (key, target, relation, directed),
            )
