from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.data.models import Provenance


class Success[T: BaseModel](BaseModel):
    kind: Literal["success"] = "success"
    data: T
    provenance: list[Provenance]


class Ambiguous(BaseModel):
    kind: Literal["ambiguous"] = "ambiguous"
    candidates: list[BaseModel]
    hint: str


class NotFound(BaseModel):
    kind: Literal["not_found"] = "not_found"
    what: str
    suggestions: list[str]


class PeriodUnavailable(BaseModel):
    kind: Literal["period_unavailable"] = "period_unavailable"
    requested: str
    available: list[str]


class UnsupportedRequest(BaseModel):
    kind: Literal["unsupported_request"] = "unsupported_request"
    reason: str


class ToolError(BaseModel):
    kind: Literal["tool_error"] = "tool_error"
    message: str
    retryable: bool


ToolResult = Annotated[
    Success[BaseModel] | Ambiguous | NotFound | PeriodUnavailable | UnsupportedRequest | ToolError,
    Field(discriminator="kind"),
]
