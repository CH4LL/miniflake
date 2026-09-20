from __future__ import annotations

from app.data.search_utils import (
    matches_all_tokens,
    query_tokens,
    search_rank,
    token_like_clauses,
    tokens_overlap,
)


def test_query_tokens_drops_stopwords_and_dedupes() -> None:
    assert query_tokens("the population of the state") == ["population", "state"]
    assert query_tokens("How many people live below the poverty line?") == [
        "people",
        "below",
        "poverty",
        "line",
    ]


def test_query_tokens_caps_count_and_keeps_order() -> None:
    assert query_tokens("alpha beta gamma delta epsilon", max_tokens=3) == [
        "alpha",
        "beta",
        "gamma",
    ]


def test_query_tokens_keeps_field_ids() -> None:
    assert query_tokens("B01003e1") == ["b01003e1"]


def test_matches_all_tokens_is_order_independent() -> None:
    name = "TOTAL POPULATION"
    assert matches_all_tokens(name, ["population", "total"])
    assert not matches_all_tokens(name, ["population", "below"])
    assert matches_all_tokens(name, [])


def test_search_rank_orders_exact_prefix_phrase_tokens() -> None:
    fields = ["TOTAL POPULATION", "B01003e1"]
    assert search_rank(fields, "total population", ["total", "population"]) == 0
    assert search_rank(fields, "total", ["total"]) == 1
    assert search_rank(fields, "population", ["population"]) == 2
    assert search_rank(fields, "population total", ["population", "total"]) == 3
    assert search_rank(fields, "zebra", ["zebra"]) == 4


def test_tokens_overlap_uses_shared_stem() -> None:
    assert tokens_overlap("educated", "education")
    assert tokens_overlap("income", "income")
    assert not tokens_overlap("median", "medical")
    assert not tokens_overlap("dog", "dogs")


def test_token_like_clauses_generate_parametrised_and_chain() -> None:
    sql, params = token_like_clauses(["poverty", "line"], "searchable")
    assert sql == (
        "(searchable LIKE '%%' || %(token_0)s || '%%' "
        "AND searchable LIKE '%%' || %(token_1)s || '%%')"
    )
    assert params == {"token_0": "poverty", "token_1": "line"}


def test_token_like_clauses_without_tokens_fall_back_to_phrase() -> None:
    sql, params = token_like_clauses([], "searchable")
    assert sql == "searchable LIKE '%%' || LOWER(%(query)s) || '%%'"
    assert params == {}
