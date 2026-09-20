from __future__ import annotations

import re

STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "did",
        "do",
        "does",
        "for",
        "from",
        "has",
        "have",
        "how",
        "in",
        "is",
        "it",
        "its",
        "live",
        "many",
        "much",
        "of",
        "on",
        "or",
        "per",
        "that",
        "the",
        "their",
        "there",
        "this",
        "to",
        "was",
        "were",
        "what",
        "which",
        "who",
        "with",
    }
)
DEFAULT_MAX_TOKENS = 6
STEM_LENGTH = 6
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def match_rank(name: str, query: str) -> int:
    name_lower = name.lower()
    query_lower = query.lower()
    if name_lower == query_lower:
        return 0
    if name_lower.startswith(query_lower):
        return 1
    if query_lower in name_lower:
        return 2
    return 3


def matches_query(name: str, query: str) -> bool:
    name_lower = name.lower()
    query_lower = query.lower()
    return (
        name_lower == query_lower or name_lower.startswith(query_lower) or query_lower in name_lower
    )


def query_tokens(query: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> list[str]:
    tokens: list[str] = []
    for token in TOKEN_PATTERN.findall(query.lower()):
        if token in STOPWORDS or token in tokens:
            continue
        tokens.append(token)
        if len(tokens) >= max_tokens:
            break
    return tokens


def matches_all_tokens(haystack: str, tokens: list[str]) -> bool:
    lowered = haystack.lower()
    return all(token in lowered for token in tokens)


def tokens_overlap(left: str, right: str) -> bool:
    if left == right:
        return True
    if len(left) < STEM_LENGTH or len(right) < STEM_LENGTH:
        return False
    return left[:STEM_LENGTH] == right[:STEM_LENGTH]


def search_rank(fields: list[str], query: str, tokens: list[str]) -> int:
    phrase_rank = min((match_rank(field, query) for field in fields), default=3)
    if phrase_rank < 3:
        return phrase_rank
    if tokens and matches_all_tokens(" ".join(fields), tokens):
        return 3
    return 4


def token_like_clauses(
    tokens: list[str], searchable_expr: str, *, param_prefix: str = "token"
) -> tuple[str, dict[str, str]]:
    if not tokens:
        return f"{searchable_expr} LIKE '%%' || LOWER(%(query)s) || '%%'", {}
    clauses: list[str] = []
    params: dict[str, str] = {}
    for index, token in enumerate(tokens):
        name = f"{param_prefix}_{index}"
        clauses.append(f"{searchable_expr} LIKE '%%' || %({name})s || '%%'")
        params[name] = token
    return "(" + " AND ".join(clauses) + ")", params
