"""
Claude Client — the bridge to the Anthropic API.

Single transport: Anthropic Messages API via raw HTTP (urllib).
No third-party dependencies. Returns token usage for tracking.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


@dataclass
class ClaudeConfig:
    """Configuration for the Claude client."""
    model: str = "claude-sonnet-4-5-20250929"
    timeout_seconds: int = 120
    max_tokens: int = 2048
    api_key: str | None = None


@dataclass
class ClaudeResponse:
    """What came back from Claude."""
    text: str
    success: bool
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


def send(
    user_message: str,
    config: ClaudeConfig | None = None,
    system_prompt: str | None = None,
) -> ClaudeResponse:
    """Send a message to Claude and get a response with token usage."""
    c = config or ClaudeConfig()

    try:
        return _send_api(user_message, c, system_prompt)
    except Exception as e:
        return ClaudeResponse(
            text="",
            success=False,
            error=str(e),
        )


def _send_api(
    user_message: str,
    config: ClaudeConfig,
    system_prompt: str | None = None,
) -> ClaudeResponse:
    """Send via Anthropic Messages API using raw HTTP."""
    api_key = config.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No API key. Set ANTHROPIC_API_KEY or api_key in config."
        )

    content = [{"type": "text", "text": user_message}]

    body: dict = {
        "model": config.model,
        "max_tokens": config.max_tokens,
        "messages": [{"role": "user", "content": content}],
    }

    if system_prompt:
        body["system"] = system_prompt

    data = json.dumps(body).encode("utf-8")

    req = Request(
        ANTHROPIC_API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=config.timeout_seconds) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Anthropic API error {e.code}: {error_body}")
    except URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")

    # Extract text from response
    text = ""
    for block in result.get("content", []):
        if block.get("type") == "text":
            text += block.get("text", "")

    # Extract token usage
    usage = result.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    return ClaudeResponse(
        text=text,
        success=True,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
