"""ForgeGod JSON extraction — robust multi-strategy pipeline for LLM responses.

Replaces the buggy greedy-regex pattern that was copy-pasted across 5 files.
Pipeline: json.loads → raw_decode → json_repair → raise ValueError.
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger("forgegod.json_utils")


def extract_json(text: str, *, expect_array: bool = False) -> dict | list:
    """Extract the first valid JSON object (or array) from LLM response text.

    Strategy:
      1. Direct json.loads (response is clean JSON)
      2. raw_decode scan (response has JSON embedded in extra text)
      3. json_repair (response has broken JSON — trailing commas, truncation, etc.)

    Args:
        text: Raw LLM response, possibly with code fences, explanation, etc.
        expect_array: If True, also try to find JSON arrays (not just objects).

    Returns:
        Parsed dict or list.

    Raises:
        ValueError: If no valid JSON could be extracted after all strategies.
    """
    if not text or not text.strip():
        raise ValueError("Empty response")

    # Pre-process: strip code fences (belt-and-suspenders with router's _strip_code_fences)
    cleaned = _strip_fences(text)

    # Strategy 1: direct parse
    try:
        result = json.loads(cleaned)
        if isinstance(result, (dict, list)):
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: raw_decode — find first valid JSON object/array
    # This is the correct replacement for the greedy regex r"\{.*\}" because
    # it uses Python's actual JSON parser and handles nested braces properly.
    decoder = json.JSONDecoder()
    targets = "{[" if expect_array else "{"
    for i, ch in enumerate(cleaned):
        if ch in targets:
            try:
                obj, _ = decoder.raw_decode(cleaned, i)
                if isinstance(obj, (dict, list)):
                    return obj
            except json.JSONDecodeError:
                continue

    # Strategy 3: json_repair — handles truncated JSON, trailing commas,
    # single quotes, missing quotes, unescaped chars, incomplete structures.
    try:
        from json_repair import repair_json

        repaired = repair_json(cleaned, return_objects=True)
        if isinstance(repaired, dict):
            return repaired
        if isinstance(repaired, list):
            if expect_array:
                return repaired
            # Sometimes repair returns a list when we want a dict —
            # check if first element is a dict (common with wrapped responses)
            if repaired and isinstance(repaired[0], dict):
                return repaired[0]
    except Exception as e:
        logger.debug("json_repair failed: %s", e)

    # Also try repair on the original (un-stripped) text
    if cleaned != text.strip():
        try:
            from json_repair import repair_json

            repaired = repair_json(text.strip(), return_objects=True)
            if isinstance(repaired, (dict, list)):
                return repaired
        except Exception:
            pass

    raise ValueError(
        f"No valid JSON found in response ({len(text)} chars, "
        f"starts with: {text[:80]!r}...)"
    )


def _strip_fences(text: str) -> str:
    """Strip markdown code fences and leading prose from LLM response."""
    stripped = text.strip()
    # Remove ```json ... ``` wrapping
    stripped = re.sub(r"^```(?:json|JSON)?\s*\n?", "", stripped)
    stripped = re.sub(r"\n?```\s*$", "", stripped)
    stripped = stripped.strip()
    return stripped
