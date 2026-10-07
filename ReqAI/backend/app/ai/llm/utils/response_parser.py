"""
response_parser.py – Safe JSON extraction from LLM text responses.

LLMs sometimes wrap JSON in markdown code fences or add preamble text.
These utilities extract and validate clean JSON regardless of formatting.
"""
from __future__ import annotations

import json
import re
from typing import Any


def extract_json(text: str) -> Any:
    """
    Extract a JSON object or array from an LLM response string.

    Handles:
      - Bare JSON
      - ```json ... ``` fences
      - ``` ... ``` fences
      - Leading/trailing prose around the JSON block

    Args:
        text: Raw LLM output string.

    Returns:
        Parsed Python object (dict or list).

    Raises:
        ValueError: If no valid JSON block can be found.
    """
    if not text or not text.strip():
        raise ValueError("LLM returned an empty response.")

    # 1. Try direct parse (ideal case)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown code fences: ```json ... ``` or ``` ... ```
    fence_pattern = re.compile(
        r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE
    )
    fence_match = fence_pattern.search(text)
    if fence_match:
        candidate = fence_match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # 3. Find the first { ... } or [ ... ] block
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        end   = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            candidate = text[start:end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    raise ValueError(
        f"Could not extract valid JSON from LLM response. "
        f"First 200 chars: {text[:200]!r}"
    )


def safe_str(value: Any, default: str = "") -> str:
    """Return a string, falling back to default if value is None or non-string."""
    if value is None:
        return default
    return str(value).strip()


def safe_list(value: Any) -> list:
    """Return a list, falling back to [] if value is None or not iterable as list."""
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]
