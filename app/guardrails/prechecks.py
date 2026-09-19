from __future__ import annotations

import re
from pathlib import Path

import yaml

from app.guardrails.types import PrecheckCategory, PrecheckResult

PATTERNS_PATH = Path(__file__).resolve().parent / "patterns.yaml"
_COMPILED: dict[PrecheckCategory, list[re.Pattern[str]]] | None = None


def load_patterns(path: Path | None = None) -> dict[str, list[str]]:
    patterns_path = path or PATTERNS_PATH
    raw = yaml.safe_load(patterns_path.read_text(encoding="utf-8"))
    return {key: [str(item) for item in value] for key, value in raw.items()}


def _compiled_patterns(
    rules: dict[str, list[str]],
) -> dict[PrecheckCategory, list[re.Pattern[str]]]:
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = {}
        for category, patterns in rules.items():
            _COMPILED[category] = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    return _COMPILED


def check_sanity(message: str, max_chars: int) -> str | None:
    normalized = message.strip()
    if not normalized:
        return "Message must not be empty"
    if len(normalized) > max_chars:
        return "Message exceeds maximum length"
    if any(ord(char) < 32 and char not in "\t\n\r" for char in normalized):
        return "Message contains invalid control characters"
    return None


def match_patterns(message: str, rules: dict[str, list[str]] | None = None) -> PrecheckResult:
    compiled = _compiled_patterns(rules or load_patterns())
    for category, patterns in compiled.items():
        for pattern in patterns:
            if pattern.search(message):
                return PrecheckResult(category=category)
    return PrecheckResult()
