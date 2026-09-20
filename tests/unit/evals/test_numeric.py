from __future__ import annotations

from evals.numeric import extract_numbers


def test_extract_numbers_handles_millions_and_percentages() -> None:
    tokens = extract_numbers("About 29.5 million people, or 9.8% of the total.")
    assert any(abs(token.value - 29_500_000) < 1 for token in tokens)
    assert any(abs(token.value - 9.8) < 0.01 for token in tokens)


def test_extract_numbers_skips_acs_field_ids() -> None:
    tokens = extract_numbers("Variable B01003e1 and series B19013.")
    values = {token.value for token in tokens}
    assert 1003.0 not in values
    assert 19013.0 not in values
    assert 1.0 not in values


def test_extract_numbers_parses_comma_separated_integers() -> None:
    tokens = extract_numbers("The population is 29,145,505.")
    assert any(abs(token.value - 29_145_505) < 1 for token in tokens)
