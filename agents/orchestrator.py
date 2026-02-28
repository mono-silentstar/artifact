"""
Orchestrator — the conversation loop.

Pipeline:
  1. Visitor sends a message
  2. Ingest it
  3. Assemble context
  4. Send to Claude
  5. Parse and ingest Claude's response
  6. Handle any recall requests
  7. Return the response with token usage
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from wake.assemble import assemble, render_system, render_user, WakeConfig
from wake.recall import recall, RecallResult, NeighborResult
from wake.schema import connect, migrate
from ingest.parse import (
    parse_visitor_message,
    parse_response,
    parse_recall_requests,
)
from ingest.lifecycle import ingest
from .claude_client import send, ClaudeConfig, ClaudeResponse


TONE_INSTRUCTIONS = {
    "casual": "Respond in a warm, conversational, accessible tone. Keep explanations simple and friendly.",
    "technical": "Respond with precision and technical detail. Use proper terminology and be thorough.",
    "creative": "Respond expressively, with vivid metaphors and poetic language. Make the architecture feel alive.",
}


@dataclass
class TurnConfig:
    """Everything needed to run a conversation turn."""
    db_path: Path
    wake_context_path: Path
    ambient_path: Path
    fragment_db_path: Path | None = None
    summaries_path: Path | None = None
    claude_config: ClaudeConfig = field(default_factory=ClaudeConfig)


@dataclass
class TurnResult:
    """What happened in a single conversation turn."""
    response_text: str
    display_text: str
    display_spans: list[dict]
    actor: str | None
    turn: int
    recall_results: list[RecallResult] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    success: bool = True
    error: str | None = None


def _load_recall_results(db_path: Path) -> list[RecallResult]:
    """Load pending recall results from the state table."""
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM state WHERE key = 'pending_recall'"
        ).fetchone()
        if not row:
            return []
        data = json.loads(row["value"])
        results = []
        for item in data:
            neighbors = [
                NeighborResult(key=n["key"], ambient=n["ambient"], relation=n["relation"])
                for n in item.get("neighbors", [])
            ]
            results.append(RecallResult(
                key=item["key"], content=item["content"],
                depth=item["depth"], neighbors=neighbors,
            ))
        return results
    finally:
        conn.close()


def _save_recall_results(db_path: Path, results: list[RecallResult]) -> None:
    """Persist recall results in state table for next turn, or clear if empty."""
    conn = connect(db_path)
    try:
        if not results:
            conn.execute("DELETE FROM state WHERE key = 'pending_recall'")
        else:
            data = [
                {
                    "key": r.key, "content": r.content, "depth": r.depth,
                    "neighbors": [
                        {"key": n.key, "ambient": n.ambient, "relation": n.relation}
                        for n in r.neighbors
                    ],
                }
                for r in results
            ]
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO state (key, value, updated_at) VALUES ('pending_recall', ?, ?)",
                (json.dumps(data), now),
            )
        conn.commit()
    finally:
        conn.close()


def turn(
    config: TurnConfig,
    message: str,
    tone: str | None = None,
) -> TurnResult:
    """
    Run a single conversation turn.

    Visitor sends a message -> Claude responds -> everything gets stored.
    """
    # Ensure schema is current
    migrate(config.db_path)

    # 1. Parse and ingest visitor's message
    visitor_parsed = parse_visitor_message(message)
    visitor_result = ingest(
        config.db_path, visitor_parsed,
        fragment_db_path=config.fragment_db_path,
    )

    # 2. Assemble context
    wake_config = WakeConfig(
        db_path=config.db_path,
        wake_context_path=config.wake_context_path,
        ambient_path=config.ambient_path,
        summaries_path=config.summaries_path,
    )

    hot = f"visitor: {message}"

    previous_recall = _load_recall_results(config.db_path)
    if previous_recall:
        _save_recall_results(config.db_path, [])  # one-shot: consumed on load

    package = assemble(
        wake_config,
        hot_context=hot,
        current_turn=visitor_result.turn,
        recall_results=previous_recall,
    )

    system_prompt = render_system(package)

    # Inject tone instruction into system prompt
    if tone and tone in TONE_INSTRUCTIONS:
        system_prompt += f"\n\n## Communication Tone\n{TONE_INSTRUCTIONS[tone]}"

    user_message = render_user(package)

    # 3. Send to Claude
    claude_response = send(
        user_message, config.claude_config,
        system_prompt=system_prompt,
    )

    if not claude_response.success:
        return TurnResult(
            response_text="",
            display_text="",
            display_spans=[],
            actor=None,
            turn=visitor_result.turn,
            success=False,
            error=claude_response.error,
        )

    # 4. Parse Claude's response
    response_parsed = parse_response(claude_response.text)

    # 5. Ingest Claude's response
    ingest(
        config.db_path, response_parsed,
        is_claude=True,
        fragment_db_path=config.fragment_db_path,
    )

    # 6. Handle recall requests
    recall_db = config.fragment_db_path or config.db_path
    recall_requests = parse_recall_requests(claude_response.text)
    recall_results = []
    for key, deep in recall_requests:
        result = recall(key, recall_db, deep=deep)
        if result:
            recall_results.append(result)

    # Save recall results for next turn's context
    _save_recall_results(config.db_path, recall_results)

    # 7. Extract display content
    display_spans = []
    display_parts = []
    for span in response_parsed.spans:
        if span.tag in ("say", "do", "narrate"):
            display_parts.append(span.content)
            display_spans.append({"tag": span.tag, "content": span.content})
    display_text = "\n".join(display_parts)

    return TurnResult(
        response_text=claude_response.text,
        display_text=display_text,
        display_spans=display_spans,
        actor=response_parsed.actor,
        turn=visitor_result.turn,
        recall_results=recall_results,
        input_tokens=claude_response.input_tokens,
        output_tokens=claude_response.output_tokens,
        success=True,
    )
