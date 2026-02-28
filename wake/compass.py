"""
Compass — the surfacing algorithm.

The Mirror compresses backward; the Compass surfaces forward.
Neither is a person. Both are infrastructure.

Each turn, the Compass scores all active working memory items by
time relevance and topic relevance, then surfaces the most important
ones that aren't already visible in Lingering. Shares a 1K token
budget with recall results (recall gets priority).

Two scoring axes:
  time_score  — proximity to due date (0.0–1.0)
  topic_score — relevance to current conversation (0.0–1.0)
  combined    — max(time, topic). Either reason alone is sufficient.

Minimum threshold: 0.15. Below this, don't surface.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .recall import RecallResult


# Minimum score to surface — below this, too noisy
SURFACE_THRESHOLD = 0.15

# Characters per token (matches assemble.py)
CHARS_PER_TOKEN = 4

# Regex to extract [bracketed] fragment keys from text
_KEY_RE = re.compile(r"\[([a-z][a-z0-9-]*)\]")


# Common words to ignore in keyword matching
_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "about", "like",
    "through", "after", "over", "between", "out", "against", "during",
    "without", "before", "under", "around", "among", "and", "but", "or",
    "nor", "not", "so", "yet", "both", "either", "neither", "each",
    "every", "all", "any", "few", "more", "most", "other", "some", "such",
    "no", "only", "own", "same", "than", "too", "very", "just", "because",
    "if", "when", "while", "how", "what", "which", "who", "whom", "this",
    "that", "these", "those", "i", "me", "my", "we", "our", "you", "your",
    "he", "him", "his", "she", "her", "it", "its", "they", "them", "their",
})


@dataclass
class SurfacedItem:
    """A WM item scored for surfacing."""
    wm_id: int
    content: str          # formatted display line (shallow or deep)
    score: float
    token_estimate: int
    blocked: bool = False  # whether this item has unresolved deps


@dataclass
class CompassResult:
    """What the Compass returns to assembly."""
    surfaced: list[SurfacedItem]
    recall_results: list[RecallResult]
    budget_used: int


def _estimate_tokens(text: str) -> int:
    return max(len(text) // CHARS_PER_TOKEN, 1)


def _extract_keys(text: str) -> set[str]:
    """Pull [bracketed] fragment keys from text."""
    return set(_KEY_RE.findall(text))


def _score_time(due: datetime | None, now: datetime) -> tuple[float, str]:
    """Score a WM item by proximity to its due date.

    Returns (score, annotation) where annotation describes the time
    phase for display. Untimed items get 0.0.
    """
    if due is None:
        return 0.0, ""

    hours_until = (due - now).total_seconds() / 3600.0

    # Overdue
    if hours_until < 0:
        hours_overdue = -hours_until
        if hours_overdue < 24:
            return 1.0, "(overdue)"
        # Gentle decay after 24h overdue
        decay = max(0.0, 1.0 - (hours_overdue - 24) / 72.0)
        if decay < SURFACE_THRESHOLD:
            return 0.0, ""
        return decay, "(overdue)"

    # Urgent: <6 hours
    if hours_until < 6:
        return 1.0, "(urgent)"

    # Approaching: <48 hours
    if hours_until < 48:
        progress = 1.0 - (hours_until / 48.0)
        score = 0.5 + 0.4 * progress
        return score, "(approaching)"

    # Gentle rise: 48h to 7 days
    if hours_until < 168:  # 7 days
        progress = 1.0 - (hours_until / 168.0)
        score = 0.1 + 0.2 * progress
        return score, "(upcoming)"

    # Far out: >7 days
    return 0.0, ""


def _score_topic(
    wm_id: int,
    wm_content: str,
    wm_subject: str | None,
    context_keys: set[str],
    context_words: set[str],
    ref_keys: dict[int, set[str]],
) -> float:
    """Score a WM item by topic relevance to current conversation.

    Three signals, max wins:
      - Fragment key match via working_memory_refs: 0.8
      - Subject word overlap with conversation: 0.4
      - Content keyword overlap: 0.2–0.5
    """
    scores = []

    # Fragment key match: WM item linked to a key mentioned in conversation
    item_keys = ref_keys.get(wm_id, set())
    if item_keys & context_keys:
        scores.append(0.8)

    # Subject match: subject words appear in conversation
    if wm_subject:
        subject_words = set(wm_subject.lower().split()) - _STOP_WORDS
        if subject_words and context_words:
            overlap = len(subject_words & context_words) / len(subject_words)
            if overlap > 0:
                scores.append(0.4 * min(overlap * 2, 1.0))

    # Content keyword overlap
    content_words = set(wm_content.lower().split()) - _STOP_WORDS
    if content_words and context_words:
        overlap = len(content_words & context_words) / len(content_words)
        if overlap > 0:
            scores.append(0.2 + 0.3 * min(overlap * 3, 1.0))

    return max(scores) if scores else 0.0


def _load_ref_keys(conn: sqlite3.Connection) -> dict[int, set[str]]:
    """Load all working_memory_refs as {wm_id: set of fragment keys}."""
    rows = conn.execute(
        "SELECT wm_id, fragment_key FROM working_memory_refs"
    ).fetchall()

    refs: dict[int, set[str]] = {}
    for row in rows:
        refs.setdefault(row["wm_id"], set()).add(row["fragment_key"])
    return refs


def _load_deps(conn: sqlite3.Connection) -> dict[int, list[int]]:
    """Load WM dependency edges: {wm_id: [blocker_id, ...]}."""
    try:
        rows = conn.execute(
            "SELECT wm_id, blocked_by FROM working_memory_deps"
        ).fetchall()
    except Exception:
        return {}  # table doesn't exist yet (pre-v4)

    deps: dict[int, list[int]] = {}
    for row in rows:
        deps.setdefault(row["wm_id"], []).append(row["blocked_by"])
    return deps


def _get_blocker_names(
    wm_id: int,
    deps: dict[int, list[int]],
    active_ids: set[int],
    wm_lookup: dict[int, sqlite3.Row],
) -> list[str]:
    """Return display names of active blockers for wm_id. Empty = unblocked."""
    blocker_ids = deps.get(wm_id, [])
    names = []
    for bid in blocker_ids:
        if bid in active_ids:
            row = wm_lookup.get(bid)
            if row:
                names.append(row["subject"] or row["content"][:40])
            else:
                names.append(f"#{bid}")
    return names


def _format_wm_shallow(row: sqlite3.Row, blocker_names: list[str]) -> str:
    """Blocked item: [type] subject (blocked by: X, Y)."""
    wm_type = row["type"]
    subject = row["subject"] or row["content"][:50]
    blockers = ", ".join(blocker_names)
    return f"[{wm_type}] {subject} (blocked by: {blockers})"


def _format_wm_deep(row: sqlite3.Row) -> str:
    """Actionable item: [type] full content, matching Lingering format."""
    wm_type = row["type"]
    actor = row["actor"] or ""
    prefix = f"[{wm_type}]"
    if actor:
        prefix = f"[{wm_type}] {actor}:"
    return f"{prefix} {row['content']}"


def _trim_recall(
    results: list[RecallResult],
    budget: int,
) -> tuple[list[RecallResult], int]:
    """Trim recall results to fit budget. Returns (selected, tokens_used)."""
    if not results:
        return [], 0

    selected = []
    used = 0

    for result in results:
        cost = _estimate_tokens(result.content)
        for n in result.neighbors:
            cost += _estimate_tokens(n.ambient)

        if cost <= budget - used:
            selected.append(result)
            used += cost

    return selected, used


def surface(
    all_wm_rows: list[sqlite3.Row],
    lingering_ids: set[int],
    hot_context: str,
    conversation: list,
    recall_results: list[RecallResult],
    conn: sqlite3.Connection,
    now: datetime,
    budget: int = 1000,
) -> CompassResult:
    """Score and surface working memory items by time and topic relevance.

    Recall results fill first (explicitly requested, always priority).
    Remaining budget goes to highest-scoring WM items not already in Lingering.
    """
    # 1. Recall results get priority — trim to budget
    trimmed_recall, recall_used = _trim_recall(recall_results, budget)
    remaining = budget - recall_used

    # 2. Build context for topic scoring
    context_text = hot_context
    for frag in conversation:
        context_text += " " + frag.content

    context_keys = _extract_keys(context_text)
    context_words = set(context_text.lower().split()) - _STOP_WORDS

    # 3. Load fragment key refs and dependency edges
    ref_keys = _load_ref_keys(conn)
    deps = _load_deps(conn)

    # Build lookup structures for dependency resolution
    active_ids = {row["id"] for row in all_wm_rows}
    wm_lookup = {row["id"]: row for row in all_wm_rows}

    # 4. Score each WM item
    scored: list[tuple[sqlite3.Row, float, str]] = []

    for row in all_wm_rows:
        wm_id = row["id"]

        # Skip items already in Lingering
        if wm_id in lingering_ids:
            continue

        # Time score
        due = None
        if row["due"]:
            due = datetime.fromisoformat(row["due"]).replace(tzinfo=timezone.utc)

        time_score, annotation = _score_time(due, now)

        # Topic score
        topic_score = _score_topic(
            wm_id=wm_id,
            wm_content=row["content"],
            wm_subject=row["subject"],
            context_keys=context_keys,
            context_words=context_words,
            ref_keys=ref_keys,
        )

        # Combined: either reason alone is sufficient
        combined = max(time_score, topic_score)

        if combined >= SURFACE_THRESHOLD:
            scored.append((row, combined, annotation))

    # 5. Sort by score descending, fill remaining budget
    scored.sort(key=lambda x: x[1], reverse=True)

    surfaced = []

    for row, score_val, annotation in scored:
        wm_id = row["id"]
        blocker_names = _get_blocker_names(wm_id, deps, active_ids, wm_lookup)
        is_blocked = len(blocker_names) > 0

        if is_blocked:
            line = _format_wm_shallow(row, blocker_names)
        else:
            line = _format_wm_deep(row)
            if annotation:
                line = f"{line} {annotation}"

        cost = _estimate_tokens(line)
        if cost <= remaining:
            surfaced.append(SurfacedItem(
                wm_id=wm_id,
                content=line,
                score=score_val,
                token_estimate=cost,
                blocked=is_blocked,
            ))
            remaining -= cost

    # 6. Sort surfaced items chronologically for natural reading
    surfaced.sort(key=lambda s: s.wm_id)

    return CompassResult(
        surfaced=surfaced,
        recall_results=trimmed_recall,
        budget_used=budget - remaining,
    )
