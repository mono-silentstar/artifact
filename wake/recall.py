"""
Recall — how I look things up.

Exact key lookup. No fuzzy matching. The keys I know come from
ambient prose — [bracketed words] that are simultaneously my
vocabulary and the database index.

Three depths:
  ambient     — always visible, never needs lookup
  recognition — shallow pull, the story of a thing
  inventory   — deep pull, the full detail

Neighbor-pull: when I recall a fragment, its graph neighbors
surface briefly at ambient depth with faster decay.

Plans: a separate lookup for working memory items. Queryable
by topic (fragment key) or time window. Bypasses submersion —
shows everything active regardless of current decay score.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path


@dataclass
class RecallResult:
    """What comes back when I tug a thread."""
    key: str
    content: str                          # the tier content I asked for
    depth: str                            # which tier was returned
    neighbors: list[NeighborResult]       # adjacent fragments, ambient tier


@dataclass
class NeighborResult:
    """A neighbor fragment surfaced by proximity."""
    key: str
    ambient: str                          # only the ambient tier
    relation: str                         # how it connects


from .schema import connect as _connect


def recall(
    key: str,
    db_path: str | Path,
    deep: bool = False,
) -> RecallResult | None:
    """
    Look up a fragment by exact key.

    Returns recognition tier by default, inventory if deep=True.
    Also pulls neighbor fragments at ambient depth.

    Returns None if the key doesn't exist — which means the ambient
    prose referenced something that isn't in the database. That's
    a sync issue the maintenance agent should catch.
    """
    conn = _connect(db_path)

    try:
        # Pull the fragment
        tier = "inventory" if deep else "recognition"
        row = conn.execute(
            "SELECT key, ambient, recognition, inventory FROM fragments WHERE key = ?",
            (key,),
        ).fetchone()

        if row is None:
            return None

        # Use requested tier, fall back to recognition, then ambient
        content = row[tier] or row["recognition"] or row["ambient"] or ""

        # Pull neighbors via edges
        edges = conn.execute(
            """
            SELECT f.key, f.ambient, e.relation
            FROM fragment_edges e
            JOIN fragments f ON f.key = e.target_key
            WHERE e.source_key = ?
            """,
            (key,),
        ).fetchall()

        neighbors = [
            NeighborResult(
                key=edge["key"],
                ambient=edge["ambient"] or "",
                relation=edge["relation"] or "",
            )
            for edge in edges
            if edge["ambient"]  # skip neighbors with no ambient content
        ]

        return RecallResult(
            key=key,
            content=content,
            depth=tier,
            neighbors=neighbors,
        )

    finally:
        conn.close()


def recall_multi(
    keys: list[str],
    db_path: str | Path,
    deep: bool = False,
) -> list[RecallResult]:
    """
    Look up multiple fragments. Deduplicates neighbors —
    if I recall decay and fragments, and they're neighbors of each other,
    each appears once as a primary result, not again as a neighbor.
    """
    results = []
    seen_keys = set()

    for key in keys:
        result = recall(key, db_path, deep=deep)
        if result is not None:
            results.append(result)
            seen_keys.add(key)

    # Deduplicate neighbors — don't surface a key as a neighbor
    # if it was already recalled directly
    for result in results:
        result.neighbors = [n for n in result.neighbors if n.key not in seen_keys]
        # Also track neighbor keys to avoid duplicates across results
        for n in result.neighbors:
            seen_keys.add(n.key)

    return results

