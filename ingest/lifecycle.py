"""
Lifecycle — managing working memory state.

When tagged content comes in, this module decides what to do:
  - Create new working memory items
  - Drop pins
  - Link items to fragment keys
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path

from wake.schema import connect, VALID_WM_TYPES, DISPLAY_TAGS
from .parse import (
    ParsedMessage,
    TaggedSpan,
    extract_fragment_keys,
)


@dataclass
class IngestResult:
    """What happened when we ingested a message."""
    event_id: int
    wm_created: list[int]
    wm_resolved: list[int]
    turn: int


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ingest(
    db_path: Path,
    parsed: ParsedMessage,
    is_claude: bool = False,
    fragment_db_path: Path | None = None,
) -> IngestResult:
    """
    Ingest a parsed message into the session database.

    1. Create event + event_tags
    2. For each tagged span, handle the lifecycle
    3. Increment turn counter (for visitor messages only)
    """
    conn = connect(db_path)
    now = _now_iso()

    wm_created = []
    wm_resolved = []

    try:
        # 1. Create event
        cursor = conn.execute(
            """INSERT INTO events (ts, content, actor)
               VALUES (?, ?, ?)""",
            (now, parsed.raw, parsed.actor),
        )
        event_id = cursor.lastrowid

        # 2. Store event tags
        all_tags = {span.tag for span in parsed.spans}
        for tag in all_tags:
            conn.execute(
                "INSERT OR IGNORE INTO event_tags (event_id, tag) VALUES (?, ?)",
                (event_id, tag),
            )

        # 3. Process each span
        for span in parsed.spans:
            if span.tag in DISPLAY_TAGS:
                continue

            if span.tag not in VALID_WM_TYPES:
                continue

            if span.modifier == "drop":
                dropped = _drop_pin(conn, span, now)
                wm_resolved.extend(dropped)
            elif span.modifier in ("resolve", "cancel"):
                resolved = _resolve_plan(conn, span, now)
                wm_resolved.extend(resolved)
            else:
                created = _create_wm_item(
                    conn, event_id, span, now, _get_turn(conn),
                    fragment_db_path=fragment_db_path,
                )
                wm_created.extend(created)

        # 4. Increment turn counter (visitor messages only)
        turn = _get_turn(conn)
        if not is_claude:
            turn += 1
            _set_turn(conn, turn)

        conn.commit()

        return IngestResult(
            event_id=event_id,
            wm_created=wm_created,
            wm_resolved=wm_resolved,
            turn=turn,
        )

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _create_wm_item(
    conn: sqlite3.Connection,
    event_id: int,
    span: TaggedSpan,
    now: str,
    turn: int | None = None,
    fragment_db_path: Path | None = None,
) -> list[int]:
    """Create a new working memory item."""
    created = []

    cursor = conn.execute("""
        INSERT INTO working_memory
            (event_id, type, content, subject, actor, status, turn,
             created_at, refreshed_at)
        VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)
    """, (event_id, span.tag, span.content, None, "artifact", turn, now, now))

    wm_id = cursor.lastrowid
    created.append(wm_id)

    # Link to fragment keys mentioned in the content
    if fragment_db_path:
        keys = extract_fragment_keys(span.content)
        if keys:
            from wake.schema import connect as _connect
            frag_conn = _connect(fragment_db_path)
            try:
                placeholders = ','.join('?' for _ in keys)
                rows = frag_conn.execute(
                    f"SELECT key FROM fragments WHERE key IN ({placeholders})",
                    list(keys),
                ).fetchall()
                valid_keys = {row["key"] for row in rows}
            finally:
                frag_conn.close()

            for key in valid_keys:
                conn.execute(
                    "INSERT OR IGNORE INTO working_memory_refs (wm_id, fragment_key) VALUES (?, ?)",
                    (wm_id, key),
                )

    return created


def _drop_pin(
    conn: sqlite3.Connection,
    span: TaggedSpan,
    now: str,
) -> list[int]:
    """Find and drop the best-matching active pin."""
    query = span.content
    if not query or not query.strip():
        row = conn.execute(
            "SELECT id FROM working_memory WHERE type = 'pin' AND status = 'active' ORDER BY created_at DESC LIMIT 1",
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE working_memory SET status = 'dropped', resolved_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            return [row["id"]]
        return []

    rows = conn.execute(
        "SELECT id, content FROM working_memory WHERE type = 'pin' AND status = 'active'",
    ).fetchall()

    if not rows:
        return []

    scored = [
        (row["id"], _fuzzy_match(query, row["content"]))
        for row in rows
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    best_id, best_score = scored[0]
    if best_score < 0.15:
        return []

    conn.execute(
        "UPDATE working_memory SET status = 'dropped', resolved_at = ? WHERE id = ?",
        (now, best_id),
    )
    return [best_id]


def _resolve_plan(
    conn: sqlite3.Connection,
    span: TaggedSpan,
    now: str,
) -> list[int]:
    """Find and resolve/cancel the best-matching active plan."""
    status = "resolved" if span.modifier == "resolve" else "dropped"
    query = span.content

    if not query or not query.strip():
        # No content — resolve the most recent active plan
        row = conn.execute(
            "SELECT id FROM working_memory WHERE type = 'plan' AND status = 'active' ORDER BY created_at DESC LIMIT 1",
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE working_memory SET status = ?, resolved_at = ? WHERE id = ?",
                (status, now, row["id"]),
            )
            return [row["id"]]
        return []

    rows = conn.execute(
        "SELECT id, content, subject FROM working_memory WHERE type = 'plan' AND status = 'active'",
    ).fetchall()

    if not rows:
        return []

    scored = [
        (row["id"], _fuzzy_match(query, (row["subject"] or "") + " " + row["content"]))
        for row in rows
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    best_id, best_score = scored[0]
    if best_score < 0.15:
        return []

    conn.execute(
        "UPDATE working_memory SET status = ?, resolved_at = ? WHERE id = ?",
        (status, now, best_id),
    )
    return [best_id]


def _fuzzy_match(query: str, candidate: str) -> float:
    """Simple word-overlap similarity."""
    q_words = set(query.lower().split())
    c_words = set(candidate.lower().split())
    if not q_words or not c_words:
        return 0.0
    overlap = q_words & c_words
    return len(overlap) / max(len(q_words), len(c_words))


def _get_turn(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT value FROM state WHERE key = 'current_turn'"
    ).fetchone()
    return int(row["value"]) if row else 0


def _set_turn(conn: sqlite3.Connection, turn: int) -> None:
    now = _now_iso()
    conn.execute("""
        INSERT INTO state (key, value, updated_at)
        VALUES ('current_turn', ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
    """, (str(turn), now, str(turn), now))
