import json
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from app.data.models import AggregationMethod, Provenance
from app.tools.results import (
    Ambiguous,
    NotFound,
    PeriodUnavailable,
    Success,
    ToolError,
    UnsupportedRequest,
)


class SampleData(BaseModel):
    name: str
    value: int


def _sample_provenance() -> Provenance:
    return Provenance(
        sql="fake://test",
        parameters={"key": "value"},
        row_count=1,
        source="fake",
        executed_at=datetime(2020, 1, 1, tzinfo=UTC),
        duration_ms=1.0,
        aggregation_method=AggregationMethod.DIRECT,
    )


@pytest.mark.parametrize(
    ("result", "expected_kind"),
    [
        (
            Success(
                data=SampleData(name="Texas", value=1),
                provenance=[_sample_provenance()],
            ),
            "success",
        ),
        (Ambiguous(candidates=[SampleData(name="A", value=1)], hint="pick one"), "ambiguous"),
        (NotFound(what="Atlantis", suggestions=["Alabama"]), "not_found"),
        (PeriodUnavailable(requested="1990", available=["2019", "2020"]), "period_unavailable"),
        (UnsupportedRequest(reason="not supported"), "unsupported_request"),
        (ToolError(message="boom", retryable=True), "tool_error"),
    ],
)
def test_result_serializes_with_kind_discriminator(result, expected_kind: str) -> None:
    payload = json.loads(result.model_dump_json())
    assert payload["kind"] == expected_kind


def test_success_provenance_round_trips() -> None:
    provenance = _sample_provenance()
    result = Success(data=SampleData(name="Texas", value=1), provenance=[provenance])
    payload = json.loads(result.model_dump_json())
    assert payload["provenance"][0]["aggregation_method"] == "direct"
    assert payload["data"]["name"] == "Texas"
