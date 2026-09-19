from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.guardrails.types import GroundingVerdict

SCALE_WORDS = {
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
}

NUMBER_PATTERN = re.compile(
    r"""
    (?P<number>
        -?\d{1,3}(?:,\d{3})+(?:\.\d+)?|
        -?\d+(?:\.\d+)?
    )
    (?:\s*(?P<scale>thousand|million|billion))?
    \s*(?P<percent>%|percent)?
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class NumericToken:
    raw: str
    value: float
    is_percent: bool


def collect_allowed_values(payloads: list[dict[str, Any]]) -> set[float]:
    values: set[float] = set()

    def walk(node: Any) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)):
            values.add(float(node))
            return
        if isinstance(node, str) and node.isdigit():
            values.add(float(node))
            return
        if isinstance(node, dict):
            for item in node.values():
                walk(item)
            return
        if isinstance(node, list):
            for item in node:
                walk(item)

    for payload in payloads:
        walk(payload)
    return values


def extract_numbers(text: str) -> list[NumericToken]:
    tokens: list[NumericToken] = []
    for match in NUMBER_PATTERN.finditer(text):
        raw_number = match.group("number")
        scale = match.group("scale")
        percent = match.group("percent")
        numeric = float(raw_number.replace(",", ""))
        if scale:
            numeric *= SCALE_WORDS[scale.lower()]
        tokens.append(
            NumericToken(
                raw=match.group(0).strip(),
                value=numeric,
                is_percent=bool(percent),
            )
        )
    return tokens


def check_grounding(
    text: str,
    payloads: list[dict[str, Any]],
    settings: Settings,
) -> GroundingVerdict:
    if not settings.guardrail_grounding_enabled:
        return GroundingVerdict(grounded=True)
    allowed = collect_allowed_values(payloads)
    if not allowed:
        return GroundingVerdict(grounded=True)
    derived = _derived_values(allowed)
    offending: list[str] = []
    for token in extract_numbers(text):
        if _is_exempt(token, settings):
            continue
        if not _matches_allowed(token, allowed, derived, settings):
            offending.append(token.raw)
    return GroundingVerdict(grounded=not offending, offending=offending)


def _derived_values(allowed: set[float]) -> set[float]:
    derived = set(allowed)
    values = list(allowed)
    for left, right in itertools.combinations(values, 2):
        derived.add(left + right)
        derived.add(abs(left - right))
        if right != 0:
            derived.add((left / right) * 100.0)
        if left != 0:
            derived.add((right / left) * 100.0)
    for total in itertools.combinations(values, 3):
        derived.add(sum(total))
    return derived


def _is_exempt(token: NumericToken, settings: Settings) -> bool:
    if token.is_percent:
        return False
    if token.value == int(token.value):
        integer = int(token.value)
        if (
            settings.guardrail_grounding_year_min
            <= integer
            <= settings.guardrail_grounding_year_max
        ):
            if len(str(integer)) == 4:
                return True
        if 0 < integer <= settings.guardrail_grounding_exempt_max_integer:
            return True
    return False


def _matches_allowed(
    token: NumericToken,
    allowed: set[float],
    derived: set[float],
    settings: Settings,
) -> bool:
    candidates = allowed | derived
    tolerance = _display_tolerance(token)
    for candidate in candidates:
        if token.is_percent:
            if abs(token.value - candidate) <= max(tolerance, 0.05):
                return True
            continue
        relative = abs(candidate) * settings.guardrail_grounding_relative_tolerance
        if abs(token.value - candidate) <= max(tolerance, relative):
            return True
    return False


def _display_tolerance(token: NumericToken) -> float:
    raw = token.raw.replace("%", "").replace("percent", "").strip().lower()
    if "." in raw:
        decimals = len(raw.split(".")[-1].replace(",", ""))
        return 0.5 * (10 ** (-decimals))
    return 0.5
