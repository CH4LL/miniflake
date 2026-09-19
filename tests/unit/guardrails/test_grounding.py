from __future__ import annotations

from typing import Any

from app.config import Settings
from app.guardrails.grounding import check_grounding, collect_allowed_values, extract_numbers


def _settings(**overrides: Any) -> Settings:
    base = {
        "SNOWFLAKE_ACCOUNT": "TEST",
        "SNOWFLAKE_USER": "TEST",
        "SNOWFLAKE_ROLE": "TEST",
        "SNOWFLAKE_WAREHOUSE": "TEST",
        "SNOWFLAKE_DATABASE": "TEST",
        "SNOWFLAKE_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
    }
    base.update(overrides)
    return Settings(**base, _env_file=None)


def test_collect_allowed_values_from_success_payloads() -> None:
    payloads = [
        {"value": 29500000.0, "vintage": 2020, "geo_id": "48"},
        {"rankings": [{"value": 1000.0}, {"value": 2000.0}]},
    ]
    values = collect_allowed_values(payloads)
    assert 29500000.0 in values
    assert 1000.0 in values
    assert 2000.0 in values


def test_extract_numbers_handles_millions_and_percentages() -> None:
    tokens = extract_numbers("About 29.5 million people, or 9.8% of the total.")
    assert any(abs(token.value - 29_500_000) < 1 for token in tokens)
    assert any(abs(token.value - 9.8) < 0.01 for token in tokens)


def test_grounding_passes_exact_value() -> None:
    payloads = [{"value": 29145505.0}]
    verdict = check_grounding(
        "The population is 29,145,505.",
        payloads,
        _settings(),
    )
    assert verdict.grounded is True


def test_grounding_passes_rounded_millions() -> None:
    payloads = [{"value": 29456000.0}]
    verdict = check_grounding(
        "About 29.5 million people live there.",
        payloads,
        _settings(),
    )
    assert verdict.grounded is True


def test_grounding_passes_derived_percentage() -> None:
    payloads = [{"value": 500.0}, {"value": 2000.0}]
    verdict = check_grounding(
        "That is 25% of the total.",
        payloads,
        _settings(),
    )
    assert verdict.grounded is True


def test_grounding_passes_derived_sum() -> None:
    payloads = [
        {"geographies": [{"value": 10_000_000.0}, {"value": 5_000_000.0}, {"value": 3_000_000.0}]}
    ]
    verdict = check_grounding(
        "Combined, they total 18 million people.",
        payloads,
        _settings(),
    )
    assert verdict.grounded is True


def test_grounding_passes_derived_difference() -> None:
    payloads = [
        {
            "geographies": [{"value": 10_000_000.0}, {"value": 4_500_000.0}],
            "absolute_difference": 5_500_000.0,
        }
    ]
    verdict = check_grounding(
        "The difference is 5.5 million.",
        payloads,
        _settings(),
    )
    assert verdict.grounded is True


def test_grounding_exempts_years_and_small_ordinals() -> None:
    payloads = [{"value": 29145505.0, "vintage": 2020}]
    verdict = check_grounding(
        "In 2020, Texas ranked 2nd with 29,145,505 people.",
        payloads,
        _settings(),
    )
    assert verdict.grounded is True


def test_grounding_fails_invented_number() -> None:
    payloads = [{"value": 29145505.0}]
    verdict = check_grounding(
        "The population is 99,999,999.",
        payloads,
        _settings(),
    )
    assert verdict.grounded is False
    assert verdict.offending
