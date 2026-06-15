"""Exponential backoff retry utilities with strict JSON handling."""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from loguru import logger as log

from config import MAX_RETRIES, RETRY_MIN_WAIT, RETRY_MAX_WAIT


def api_retry_decorator():
    """Standard retry decorator for API calls: exponential backoff, max 3 retries."""
    return retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type((
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.HTTPStatusError,
            json.JSONDecodeError,
        )),
        before_sleep=before_sleep_log(log, "DEBUG"),
        reraise=True,
    )


def retry_with_json_fallback(
    func: Callable[[], str],
    max_attempts: int = 2,
) -> str:
    """Call an LLM function, validate JSON, retry once with 'OUTPUT JSON ONLY' if invalid.

    Args:
        func: Callable that returns a raw text response from the LLM.
        max_attempts: Max attempts (default 2: original + 1 retry).

    Returns:
        Validated JSON string.

    Raises:
        ValueError: If all attempts produce invalid JSON.
    """
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            raw = func()
            parsed = json.loads(raw)
            return json.dumps(parsed, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            log.warning(
                "JSON validation failed (attempt {}/{}): {}",
                attempt, max_attempts, e,
            )
            if attempt < max_attempts:
                log.info("Re-prompting with 'OUTPUT JSON ONLY'")
    raise ValueError(
        f"Failed to produce valid JSON after {max_attempts} attempts: {last_error}",
    )


def extract_json_from_text(text: str) -> Optional[str]:
    """Extract a JSON object from text that may contain markdown fences or prose."""
    # Try parsing the whole text first
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fences
    import re
    patterns = [
        r"```(?:json)?\s*\n?(.*?)```",
        r"```\s*\n?(.*?)```",
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.DOTALL)
        for m in matches:
            m = m.strip()
            try:
                json.loads(m)
                return m
            except json.JSONDecodeError:
                continue

    # Try to find a top-level JSON object or array
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == start_char:
                depth += 1
            elif text[i] == end_char:
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        break
    return None
