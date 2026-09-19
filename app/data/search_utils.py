from __future__ import annotations


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
        name_lower == query_lower
        or name_lower.startswith(query_lower)
        or query_lower in name_lower
    )
