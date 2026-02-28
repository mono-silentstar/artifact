"""
Mirror Agent — the one who reflects the past.

Reads raw conversation events, routes through a multi-model pipeline
based on DO-density, and produces summaries + tag suggestions.
Output goes to summaries.sqlite, never touches the Crystal.

Pipeline:
  2-pass (DO <= 40%): Haiku clean -> Opus summarize+tag
  3-pass (DO > 40%): Haiku clean -> Sonnet compress DO -> Opus summarize+tag
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .claude_client import ClaudeConfig, send as claude_send
from .runner import Agent, AgentResult
from wake.schema import connect
from wake.summaries_schema import connect_summaries, migrate_summaries


log = logging.getLogger(__name__)

# Models for each pipeline pass
MODEL_HAIKU = "claude-haiku-4-5-20251001"
MODEL_SONNET = "claude-sonnet-4-5-20250929"
MODEL_OPUS = "claude-opus-4-6"

# DO-density threshold for routing
DO_DENSITY_THRESHOLD = 0.40

# Buffer overlap: read this many events before the compression window
OVERLAP_EVENTS = 5

# Max tags per chunk
MAX_TAGS_PER_CHUNK = 5

# Timeout for each API call (5 minutes)
PASS_TIMEOUT = 300

# Max tokens per pass
PASS_MAX_TOKENS = {
    "cleanup": 8192,
    "do_compress": 8192,
    "summarize": 4096,
}


def calculate_do_density(events: list[sqlite3.Row]) -> float:
    """Calculate DO-density: chars inside <do> tags / total display tag chars.

    Visitor messages (actor not Claude/system) count all content as display.
    """
    do_chars = 0
    display_chars = 0

    for event in events:
        content = event["content"] or ""
        actor = event["actor"]

        # Claude's responses — check display tags
        if actor is None or actor in ("claude", "artifact"):
            pass
        elif actor == "system":
            continue  # skip system events
        else:
            # Visitor's message — count all content as display
            display_chars += len(content)
            continue

        # Count chars inside display tags for Claude's responses
        for tag in ("say", "do", "narrate"):
            for match in re.finditer(
                rf"<{tag}>(.*?)</{tag}>", content, re.DOTALL
            ):
                tag_content = match.group(1)
                display_chars += len(tag_content)
                if tag == "do":
                    do_chars += len(tag_content)

    if display_chars == 0:
        return 0.0
    return do_chars / display_chars


def format_events_for_prompt(
    events: list[sqlite3.Row],
    section: str = "COMPRESS",
) -> str:
    """Format events into the prompt format the Mirror expects."""
    lines = []
    lines.append(f"## {section}")

    for event in events:
        ts = event["ts"] or ""
        actor = event["actor"] or "unknown"
        content = event["content"] or ""

        # Get tags from the event if available
        tags_str = event["tags"] if "tags" in event.keys() else ""
        tag_list = f" [{tags_str}]" if tags_str else ""

        lines.append(f"\n[{ts}] ({actor}){tag_list}")
        lines.append(content)

    return "\n".join(lines)


def parse_summary_output(text: str) -> tuple[str | None, list[dict]]:
    """Parse Opus output into summary content and tag suggestions.

    Returns (summary_text, list_of_tags).
    """
    # Extract summary
    summary_match = re.search(
        r"<summary>(.*?)</summary>", text, re.DOTALL
    )
    summary = summary_match.group(1).strip() if summary_match else None

    # Extract tags
    tags = []
    tags_match = re.search(r"<tags>(.*?)</tags>", text, re.DOTALL)
    if tags_match:
        raw = tags_match.group(1).strip()
        # Strip markdown fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                valid_types = {"pin", "pattern", "desc"}
                for tag in parsed[:MAX_TAGS_PER_CHUNK]:
                    if (
                        isinstance(tag, dict)
                        and tag.get("type") in valid_types
                        and tag.get("content")
                    ):
                        tags.append({
                            "type": tag["type"],
                            "content": tag["content"],
                            "subject": tag.get("subject"),
                        })
        except json.JSONDecodeError:
            pass

    return summary, tags


# Trigger: fire when conversation tokens since last summary exceed threshold.
# Simple, predictable, frequent. More compression = smaller batches = fresher memory.
TRIGGER_TOKEN_THRESHOLD = 1500   # conversation tokens since last fire
TRIGGER_MIN_EVENTS = 3           # absolute floor before checking

CHARS_PER_TOKEN = 4


def should_fire_mirror(mem_conn: sqlite3.Connection, sum_conn: sqlite3.Connection) -> bool:
    """Determine whether the Mirror should run.

    Fires when accumulated conversation tokens since last summary exceed
    the threshold. Simple token-volume trigger.
    """
    # Find where we left off — latest rolling summary
    last_row = sum_conn.execute(
        "SELECT chunk_end FROM summaries ORDER BY id DESC LIMIT 1"
    ).fetchone()
    since_id = last_row["chunk_end"] if last_row else 0

    # Count new events — fast check before loading anything
    new_count = mem_conn.execute(
        "SELECT COUNT(*) as cnt FROM events WHERE id > ?", (since_id,)
    ).fetchone()["cnt"]

    if new_count < TRIGGER_MIN_EVENTS:
        return False

    # Load new events for token counting
    new_events = mem_conn.execute("""
        SELECT id, content
        FROM events WHERE id > ?
        ORDER BY id ASC
    """, (since_id,)).fetchall()

    total_chars = sum(len(e["content"] or "") for e in new_events)
    estimated_tokens = total_chars // CHARS_PER_TOKEN

    return estimated_tokens >= TRIGGER_TOKEN_THRESHOLD


class MirrorAgent(Agent):
    """Compress conversation events into summaries + tag suggestions."""

    name = "mirror"
    run_type = "mirror"

    def __init__(
        self,
        db_path: Path,
        summaries_path: Path | None = None,
        prompt_dir: Path | None = None,
        api_key: str | None = None,
        dry_run: bool = False,
    ):
        super().__init__(db_path)
        self.summaries_path = summaries_path or db_path.parent / "summaries.sqlite"
        self.prompt_dir = prompt_dir or Path(__file__).resolve().parents[1] / "mdfiles" / "claude"
        self.api_key = api_key
        self.dry_run = dry_run

    def run(self, conn: sqlite3.Connection) -> AgentResult:
        result = AgentResult()

        # Ensure summaries schema exists
        migrate_summaries(self.summaries_path)
        sum_conn = connect_summaries(self.summaries_path)

        try:
            return self._run_inner(conn, sum_conn, result)
        finally:
            sum_conn.close()

    def _run_inner(
        self,
        conn: sqlite3.Connection,
        sum_conn: sqlite3.Connection,
        result: AgentResult,
    ) -> AgentResult:
        # Load the latest rolling summary (if any)
        prior_row = sum_conn.execute("""
            SELECT id, chunk_start, chunk_end, content, generation
            FROM summaries
            ORDER BY id DESC LIMIT 1
        """).fetchone()

        since_id = prior_row["chunk_end"] if prior_row else 0
        prior_summary = prior_row["content"] if prior_row else None
        prior_generation = prior_row["generation"] if prior_row else 0
        prior_start = prior_row["chunk_start"] if prior_row else None

        # Load uncompressed events
        events = conn.execute("""
            SELECT e.id, e.ts, e.content, e.actor,
                   GROUP_CONCAT(t.tag) as tags
            FROM events e
            LEFT JOIN event_tags t ON t.event_id = e.id
            WHERE e.id > ?
            GROUP BY e.id
            ORDER BY e.id ASC
        """, (since_id,)).fetchall()

        if not events:
            result.notes.append("No uncompressed events.")
            return result

        result.notes.append(f"Found {len(events)} uncompressed events (after event {since_id}).")
        if prior_summary:
            result.notes.append(f"Prior summary: generation {prior_generation}, events {prior_start}-{since_id}.")

        # Load overlap events for context
        overlap = []
        if since_id > 0:
            overlap = conn.execute("""
                SELECT e.id, e.ts, e.content, e.actor,
                       GROUP_CONCAT(t.tag) as tags
                FROM events e
                LEFT JOIN event_tags t ON t.event_id = e.id
                WHERE e.id > ? AND e.id <= ?
                GROUP BY e.id
                ORDER BY e.id ASC
            """, (max(0, since_id - OVERLAP_EVENTS), since_id)).fetchall()

        # Calculate DO-density
        density = calculate_do_density(events)
        pipeline = "3-pass" if density > DO_DENSITY_THRESHOLD else "2-pass"

        result.notes.append(
            f"DO-density: {density:.1%} -> {pipeline} pipeline."
        )

        # Rolling window: chunk_start stretches back to beginning
        chunk_start = prior_start if prior_start is not None else events[0]["id"]
        chunk_end = events[-1]["id"]
        generation = (prior_generation + 1) if prior_summary else 0

        if self.dry_run:
            result.notes.append(
                f"DRY RUN: Would compress events {chunk_start}-{chunk_end} "
                f"({len(events)} new events, generation {generation}, {pipeline})."
            )
            return result

        # Build prompt input
        context_section = ""
        if overlap:
            context_section = format_events_for_prompt(overlap, "CONTEXT") + "\n\n"
        compress_section = format_events_for_prompt(events, "COMPRESS")
        full_input = context_section + compress_section

        # Run pipeline
        summary_text, tags = self._run_pipeline(
            full_input, density, pipeline, result,
            prior_summary=prior_summary,
        )

        if summary_text is None:
            result.errors.append("Pipeline produced no summary.")
            return result

        # Estimate tokens (rough: 4 chars per token)
        token_estimate = len(summary_text) // 4

        # Store in summaries.sqlite
        now = datetime.now(timezone.utc).isoformat()

        cursor = sum_conn.execute("""
            INSERT INTO summaries
                (level, chunk_start, chunk_end, content, tokens,
                 do_density, pipeline, generation, created_at)
            VALUES ('L0', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chunk_start, chunk_end, summary_text, token_estimate,
            density, pipeline, generation, now,
        ))
        summary_id = cursor.lastrowid

        # Store tag suggestions
        for tag in tags:
            sum_conn.execute("""
                INSERT INTO tag_suggestions
                    (summary_id, type, content, subject, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                summary_id, tag["type"], tag["content"],
                tag.get("subject"), now,
            ))

        sum_conn.commit()

        result.notes.append(
            f"Stored summary (events {chunk_start}-{chunk_end}, "
            f"generation {generation}, ~{token_estimate} tokens, {len(tags)} tags)."
        )

        # Run decay sweep — mark dead WM items after compression
        try:
            self._run_decay_sweep(conn, result)
        except Exception as e:
            result.errors.append(f"Decay sweep failed: {e}")

        return result

    def _run_decay_sweep(
        self,
        conn: sqlite3.Connection,
        result: AgentResult,
    ) -> None:
        """Mark low-scoring WM items as decayed."""
        from wake.decay import sweep_decayed

        row = conn.execute(
            "SELECT value FROM state WHERE key = 'current_turn'"
        ).fetchone()
        current_turn = int(row["value"]) if row else 0

        now = datetime.now(timezone.utc)
        marked = sweep_decayed(conn, now, current_turn)
        if marked:
            result.notes.append(f"Decay sweep: marked {marked} items as decayed.")

    def _run_pipeline(
        self,
        text: str,
        density: float,
        pipeline: str,
        result: AgentResult,
        prior_summary: str | None = None,
    ) -> tuple[str | None, list[dict]]:
        """Run the multi-pass compression pipeline.

        Returns (summary_text, tags) or (None, []) on failure.
        """
        current = text

        # Pass 1 (always): Haiku cleanup
        cleanup_prompt = self._load_prompt("mirror-cleanup.md")
        result.notes.append("Pass 1: Haiku cleanup...")
        response = claude_send(
            current,
            config=ClaudeConfig(
                model=MODEL_HAIKU,
                timeout_seconds=PASS_TIMEOUT,
                max_tokens=PASS_MAX_TOKENS["cleanup"],
                api_key=self.api_key,
            ),
            system_prompt=cleanup_prompt,
        )
        if not response.success:
            result.errors.append(f"Pass 1 (Haiku) failed: {response.error}")
            return None, []
        current = response.text
        result.notes.append(f"Pass 1 done ({len(current)} chars).")

        # Pass 2 (3-pass only): Sonnet DO compression
        if pipeline == "3-pass":
            do_compress_prompt = self._load_prompt("mirror-do-compress.md")
            result.notes.append("Pass 2: Sonnet DO compression...")
            response = claude_send(
                current,
                config=ClaudeConfig(
                    model=MODEL_SONNET,
                    timeout_seconds=PASS_TIMEOUT,
                    max_tokens=PASS_MAX_TOKENS["do_compress"],
                    api_key=self.api_key,
                ),
                system_prompt=do_compress_prompt,
            )
            if not response.success:
                result.errors.append(f"Pass 2 (Sonnet) failed: {response.error}")
                return None, []
            current = response.text
            result.notes.append(f"Pass 2 done ({len(current)} chars).")

        # Prepend prior summary if rolling
        if prior_summary:
            current = f"## PRIOR\n\n{prior_summary}\n\n{current}"

        # Final pass (always): Opus summarize + tag
        summarize_prompt = self._load_prompt("mirror-summarize.md")
        result.notes.append("Final pass: Opus summarize + tag...")
        response = claude_send(
            current,
            config=ClaudeConfig(
                model=MODEL_OPUS,
                timeout_seconds=PASS_TIMEOUT,
                max_tokens=PASS_MAX_TOKENS["summarize"],
                api_key=self.api_key,
            ),
            system_prompt=summarize_prompt,
        )
        if not response.success:
            result.errors.append(f"Final pass (Opus) failed: {response.error}")
            return None, []
        result.notes.append(f"Final pass done ({len(response.text)} chars).")

        return parse_summary_output(response.text)

    def _load_prompt(self, filename: str) -> str:
        path = self.prompt_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Mirror prompt not found: {path}")
        return path.read_text(encoding="utf-8")
