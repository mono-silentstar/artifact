"""
Parse — extracting tagged content from messages.

Claude's responses contain inline tags:
  <say>hello</say>
  <thought>interesting architecture question</thought>
  <pin>visitor asked about decay curves</pin>
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from wake.schema import (
    VALID_WM_TYPES,
    DISPLAY_TAGS,
    ALL_TAGS,
)


@dataclass
class TaggedSpan:
    """A single tagged region extracted from text."""
    tag: str
    content: str
    modifier: str | None = None


@dataclass
class ParsedMessage:
    """A fully parsed message."""
    actor: str | None = None
    spans: list[TaggedSpan] = field(default_factory=list)
    untagged: str = ""
    raw: str = ""


# Lifecycle modifiers — words at the start of tag content that change behavior
PLAN_RESOLVE_WORDS = frozenset({"done", "complete", "finished"})
PLAN_CANCEL_WORDS = frozenset({"cancel", "skip", "drop", "abandon"})
PIN_DROP_WORDS = frozenset({"drop", "release", "clear", "remove"})


def _extract_modifier(tag: str, content: str) -> tuple[str | None, str]:
    """Check if content starts with a lifecycle modifier word.

    Returns (modifier, remaining_content).
    """
    stripped = content.strip()
    first_word = stripped.split(None, 1)[0].lower() if stripped else ""

    if tag == "plan":
        if first_word in PLAN_RESOLVE_WORDS:
            rest = stripped.split(None, 1)[1] if " " in stripped else ""
            return "resolve", rest.strip()
        if first_word in PLAN_CANCEL_WORDS:
            rest = stripped.split(None, 1)[1] if " " in stripped else ""
            return "cancel", rest.strip()

    if tag == "pin":
        if first_word in PIN_DROP_WORDS:
            rest = stripped.split(None, 1)[1] if " " in stripped else ""
            return "drop", rest.strip()

    return None, content


TAG_PATTERN = re.compile(
    r"<(" + "|".join(re.escape(t) for t in ALL_TAGS) + r")>"
    r"(.*?)"
    r"</\1>",
    re.DOTALL,
)


def parse_response(text: str) -> ParsedMessage:
    """Parse a Claude response for all tagged content."""
    raw = text

    spans = []
    for match in TAG_PATTERN.finditer(text):
        tag = match.group(1)
        content = match.group(2).strip()

        modifier, clean_content = _extract_modifier(tag, content)

        spans.append(TaggedSpan(
            tag=tag,
            content=clean_content,
            modifier=modifier,
        ))

    untagged = TAG_PATTERN.sub("", text).strip()

    return ParsedMessage(
        actor="artifact",
        spans=spans,
        untagged=untagged,
        raw=raw,
    )


def parse_visitor_message(text: str) -> ParsedMessage:
    """Parse a visitor's message. Simple text, no tags."""
    return ParsedMessage(
        actor="visitor",
        spans=[TaggedSpan(tag="say", content=text)],
        untagged=text,
        raw=text,
    )


def extract_fragment_keys(text: str) -> list[str]:
    """Find [bracketed-keys] in text that reference fragment keys."""
    return re.findall(r"\[([a-z][a-z0-9\-]*)\]", text)


def parse_recall_requests(text: str) -> list[tuple[str, bool]]:
    """Extract recall() calls from Claude's response text."""
    pattern = re.compile(
        r'recall\(\s*'
        r'(?:["\']([^"\']+)["\']|([a-z][a-z0-9_-]*))'
        r'\s*(?:,\s*deep\s*=\s*(True|true))?\s*\)',
    )

    results = []
    for match in pattern.finditer(text):
        key = match.group(1) or match.group(2)
        deep = match.group(3) is not None
        results.append((key, deep))

    return results
