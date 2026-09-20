from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings
from app.guardrails.types import INTENTS, IntentDecision
from app.llm.client import LLMClient
from app.llm.errors import LLMError
from app.llm.types import Message, TextBlock, ToolSchema, ToolUseBlock

logger = logging.getLogger(__name__)

CLASSIFY_TOOL_NAME = "classify_intent"
CLASSIFY_SYSTEM_PROMPT = """You classify user messages for a US census data assistant.

Return classify_intent with:
- intent: in_scope, capability, needs_clarification, off_topic, or harmful
- reason: brief internal rationale
- confidence: 0 to 1
- missing: geography, measure, vintage, generic, or none

in_scope: US population or demographic questions, including:
- named population questions (total population is a complete measure; do not ask which measure)
- omitted vintage: default is the latest ACS 5-year release; do not flag omitted vintage
- named years, including out-of-range years — the agent will explain coverage
- measures not in ACS (IQ, pet ownership, crime) — the agent will search the catalog
- unsupported geographies (city, metro/CBSA, tract) — the agent will explain limits
- projection requests — the agent will explain coverage
- ambiguous place names without place-level data — the agent will explain limits
- follow-ups that rely on prior conversation context

capability: questions about the assistant itself rather than about data values, such as
"what can you answer?", "where does the data come from", "which years do you cover",
"what geographies do you support". These are not off_topic and need no data lookup.
A question that asks for a figure is in_scope, not capability.

needs_clarification: in-scope census question that omits geography or a genuinely
underspecified measure, or names an ambiguous supported geography. Examples: no place
named; "income" without household vs family vs per capita; "how educated";
"which state is the best?"; "Washington" (state vs DC vs county); "Orange County"
(multiple states). Do NOT use for omitted vintage, named population questions,
named years, projections, metro/CBSA/city/tract/street geographies, or place names
this dataset cannot resolve.

off_topic: unrelated requests (poems, coding help, non-US geography).
Do not mark census-topic questions as off_topic just because the measure is absent (IQ, pets)
or because the topic is crime rather than demographics. Capability questions are capability,
not off_topic.

harmful: personal data requests, discriminatory framing, or dangerous instructions.
Crime-rate questions are in_scope, not harmful, when the user asks for statistics.
"""


def render_context(messages: list[Message], max_turns: int) -> str:
    if not messages or max_turns <= 0:
        return ""
    lines: list[str] = []
    turn_count = 0
    for message in reversed(messages):
        if message.role not in {"user", "assistant"}:
            continue
        text_parts = [
            block.text
            for block in message.content
            if isinstance(block, TextBlock) and block.text.strip()
        ]
        if not text_parts:
            continue
        role = "User" if message.role == "user" else "Assistant"
        lines.insert(0, f"{role}: {' '.join(text_parts)}")
        turn_count += 1
        if turn_count >= max_turns:
            break
    return "\n".join(lines)


class IntentClassifier:
    def __init__(self, llm: LLMClient, settings: Settings) -> None:
        self._llm = llm
        self._settings = settings
        self._tool = ToolSchema(
            name=CLASSIFY_TOOL_NAME,
            description="Classify the user's intent for the census assistant.",
            input_schema={
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "enum": sorted(INTENTS),
                    },
                    "reason": {"type": "string"},
                    "confidence": {"type": "number"},
                    "missing": {
                        "type": "string",
                        "enum": ["geography", "measure", "vintage", "generic", "none"],
                    },
                },
                "required": ["intent", "reason", "confidence", "missing"],
                "additionalProperties": False,
            },
        )

    def classify(self, message: str, context_excerpt: str) -> IntentDecision:
        if not self._settings.guardrail_classifier_enabled:
            return IntentDecision(intent="in_scope")
        user_content = message.strip()
        if context_excerpt:
            user_content = f"Recent conversation:\n{context_excerpt}\n\nCurrent message:\n{message}"
        try:
            response = self._llm.complete(
                CLASSIFY_SYSTEM_PROMPT,
                [Message(role="user", content=[TextBlock(text=user_content)])],
                [self._tool],
                timeout_s=self._settings.guardrail_classifier_timeout_seconds,
            )
        except LLMError as exc:
            logger.warning("Intent classifier failed open: %s", exc)
            return IntentDecision(intent="in_scope", failed_open=True)
        parsed = self._parse_response(response)
        if parsed is None:
            logger.warning("Intent classifier returned unparseable output; failing open")
            return IntentDecision(intent="in_scope", failed_open=True)
        return self._apply_threshold(parsed)

    def _parse_response(self, response: Any) -> IntentDecision | None:
        for block in response.content:
            if isinstance(block, ToolUseBlock) and block.name == CLASSIFY_TOOL_NAME:
                return self._from_payload(block.input)
        for block in response.content:
            if isinstance(block, TextBlock):
                try:
                    payload = json.loads(block.text)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    return self._from_payload(payload)
        return None

    def _from_payload(self, payload: dict[str, Any]) -> IntentDecision | None:
        intent = payload.get("intent")
        if intent not in INTENTS:
            return None
        missing = payload.get("missing")
        if missing in {"none", None, ""}:
            missing = None
        elif missing not in {"geography", "measure", "vintage", "generic"}:
            missing = "generic" if intent == "needs_clarification" else None
        confidence = float(payload.get("confidence", 0.0))
        return IntentDecision(
            intent=intent,
            reason=str(payload.get("reason", "")),
            confidence=confidence,
            missing=missing,
        )

    def _apply_threshold(self, decision: IntentDecision) -> IntentDecision:
        if (
            decision.intent == "in_scope"
            and decision.confidence < self._settings.guardrail_classifier_confidence_threshold
        ):
            return IntentDecision(
                intent="needs_clarification",
                reason=decision.reason,
                confidence=decision.confidence,
                missing=decision.missing or "generic",
            )
        return decision
