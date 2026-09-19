from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agent.prompt import load_templates
from app.data.models import Provenance
from app.llm.types import Usage
from app.tools.results import (
    Ambiguous,
    NotFound,
    PeriodUnavailable,
    Success,
    ToolError,
    ToolResult,
    UnsupportedRequest,
)

NUMERIC_TOKEN = re.compile(r"\d")


class ToolCallTrace(BaseModel):
    name: str
    input: dict[str, Any] = Field(default_factory=dict)
    result_kind: str
    duration_ms: float


class AgentAnswer(BaseModel):
    text: str
    outcome: Literal["answer", "clarify", "unanswerable", "refuse", "error"]
    provenance: list[Provenance] = Field(default_factory=list)
    tool_calls: list[ToolCallTrace] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)


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
    ) -> AgentAnswer:
        if stop_reason in {"timeout", "iteration_cap", "llm_error"}:
            template_key = stop_reason if stop_reason != "llm_error" else "llm_error"
            return AgentAnswer(
                text=self._render(template_key, tool_traces),
                outcome="error",
                provenance=provenance,
                tool_calls=tool_traces,
                usage=usage,
            )

        if tool_traces and tool_traces[-1].result_kind == "tool_error":
            return AgentAnswer(
                text=self._render("tool_error", tool_traces),
                outcome="error",
                provenance=provenance,
                tool_calls=tool_traces,
                usage=usage,
            )

        if not tool_traces:
            text = "\n".join(part.strip() for part in text_blocks if part.strip())
            if contains_numeric_token(text):
                return AgentAnswer(
                    text=self._templates["ungrounded_numeric"],
                    outcome="unanswerable",
                    provenance=[],
                    tool_calls=tool_traces,
                    usage=usage,
                )
            return AgentAnswer(
                text=text,
                outcome="answer",
                provenance=[],
                tool_calls=tool_traces,
                usage=usage,
            )

        kinds = [trace.result_kind for trace in tool_traces]
        text = "\n".join(part.strip() for part in text_blocks if part.strip())

        if any(kind == "success" for kind in kinds):
            return AgentAnswer(
                text=text,
                outcome="answer",
                provenance=provenance,
                tool_calls=tool_traces,
                usage=usage,
            )
        if kinds and all(kind == "ambiguous" for kind in kinds):
            return AgentAnswer(
                text=text,
                outcome="clarify",
                provenance=provenance,
                tool_calls=tool_traces,
                usage=usage,
            )
        unavailable_kinds = {"not_found", "period_unavailable", "unsupported_request"}
        if kinds and all(kind in unavailable_kinds for kind in kinds):
            return AgentAnswer(
                text=text,
                outcome="unanswerable",
                provenance=provenance,
                tool_calls=tool_traces,
                usage=usage,
            )

        return AgentAnswer(
            text=text or self._templates["ungrounded_numeric"],
            outcome="unanswerable",
            provenance=provenance,
            tool_calls=tool_traces,
            usage=usage,
        )

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


def contains_numeric_token(text: str) -> bool:
    return bool(NUMERIC_TOKEN.search(text))


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
