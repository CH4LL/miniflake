from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agent.prompt import load_templates
from app.data.models import Provenance
from app.llm.types import Message, Usage
from app.tools.results import (
    Ambiguous,
    NotFound,
    PeriodUnavailable,
    Success,
    ToolError,
    ToolResult,
    UnsupportedRequest,
)

DATA_TOOL_NAMES = frozenset({"get_value", "rank_geographies", "compare", "get_trend"})
UNAVAILABLE_KINDS = frozenset(
    {"not_found", "period_unavailable", "unsupported_request"},
)


class ToolCallTrace(BaseModel):
    name: str
    input: dict[str, Any] = Field(default_factory=dict)
    result_kind: str
    duration_ms: float
    data: dict[str, Any] | None = None


class AgentAnswer(BaseModel):
    text: str
    outcome: Literal["answer", "clarify", "unanswerable", "refuse", "error"]
    provenance: list[Provenance] = Field(default_factory=list)
    tool_calls: list[ToolCallTrace] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    transcript: list[Message] = Field(default_factory=list)
    stop_reason: Literal["end_turn", "timeout", "iteration_cap", "llm_error"] | None = None


class AnswerComposer:
    def __init__(self, templates: dict[str, str] | None = None) -> None:
        self._templates = templates or load_templates()

    def compose(
        self,
        *,
        stop_reason: Literal["end_turn", "timeout", "iteration_cap", "llm_error"],
        text_blocks: list[str],
        tool_traces: list[ToolCallTrace],
        provenance: list[Provenance],
        usage: Usage,
        ungrounded_answer_allowed: bool = False,
    ) -> AgentAnswer:
        if stop_reason in {"timeout", "iteration_cap", "llm_error"}:
            template_key = stop_reason if stop_reason != "llm_error" else "llm_error"
            return AgentAnswer(
                text=self._render(template_key, tool_traces),
                outcome="error",
                provenance=provenance,
                tool_calls=tool_traces,
                usage=usage,
                stop_reason=stop_reason,
            )

        if tool_traces and tool_traces[-1].result_kind == "tool_error":
            return AgentAnswer(
                text=self._render("tool_error", tool_traces),
                outcome="error",
                provenance=provenance,
                tool_calls=tool_traces,
                usage=usage,
                stop_reason=stop_reason,
            )

        text = "\n".join(part.strip() for part in text_blocks if part.strip())
        if not tool_traces:
            return AgentAnswer(
                text=text,
                outcome="answer" if ungrounded_answer_allowed else "unanswerable",
                provenance=[],
                tool_calls=tool_traces,
                usage=usage,
                stop_reason=stop_reason,
            )

        outcome = self._outcome_from_traces(tool_traces)
        return AgentAnswer(
            text=text,
            outcome=outcome,
            provenance=provenance,
            tool_calls=tool_traces,
            usage=usage,
            stop_reason=stop_reason,
        )

    def _outcome_from_traces(
        self, tool_traces: list[ToolCallTrace]
    ) -> Literal["answer", "clarify", "unanswerable"]:
        data_traces = [trace for trace in tool_traces if trace.name in DATA_TOOL_NAMES]
        if data_traces:
            kinds = [trace.result_kind for trace in data_traces]
        else:
            kinds = [trace.result_kind for trace in tool_traces]
            if kinds and all(kind == "ambiguous" for kind in kinds):
                return "clarify"
            if any(kind == "ambiguous" for kind in kinds):
                return "clarify"
            return "unanswerable"

        if any(kind == "success" for kind in kinds):
            return "answer"
        if kinds and all(kind == "ambiguous" for kind in kinds):
            return "clarify"
        if kinds and all(kind in UNAVAILABLE_KINDS for kind in kinds):
            return "unanswerable"
        return "unanswerable"

    def _render(self, template_key: str, tool_traces: list[ToolCallTrace]) -> str:
        template = self._templates[template_key]
        attempted = ", ".join(
            f"{trace.name} ({self._format_input(trace.input)})" for trace in tool_traces
        )
        return template.replace("{{ attempted }}", attempted or "none")

    @staticmethod
    def _format_input(raw_input: dict[str, Any]) -> str:
        if not raw_input:
            return "no input"
        parts = [f"{key}={value}" for key, value in raw_input.items()]
        return ", ".join(parts[:3])


def result_kind(result: ToolResult) -> str:
    if isinstance(result, Success):
        return "success"
    if isinstance(result, Ambiguous):
        return "ambiguous"
    if isinstance(result, NotFound):
        return "not_found"
    if isinstance(result, PeriodUnavailable):
        return "period_unavailable"
    if isinstance(result, UnsupportedRequest):
        return "unsupported_request"
    if isinstance(result, ToolError):
        return "tool_error"
    raise TypeError(f"Unsupported tool result type: {type(result)!r}")
