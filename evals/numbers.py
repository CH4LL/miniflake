from __future__ import annotations

import re
from dataclasses import dataclass

SCALE_WORDS = {
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
}

ACS_FIELD_ID_PATTERN = re.compile(r"\bB\d{5}(?:[eE]\d+)?\b", re.IGNORECASE)
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


def extract_numbers(text: str) -> list[NumericToken]:
    masked = ACS_FIELD_ID_PATTERN.sub(" ", text)
    tokens: list[NumericToken] = []
    for match in NUMBER_PATTERN.finditer(masked):
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
