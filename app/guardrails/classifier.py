from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings
from app.guardrails.types import IntentDecision
from app.llm.client import LLMClient
from app.llm.errors import LLMError
from app.llm.types import Message, TextBlock, ToolSchema, ToolUseBlock

logger = logging.getLogger(__name__)

CLASSIFY_TOOL_NAME = "classify_intent"
CLASSIFY_SYSTEM_PROMPT = """You classify user messages for a US census data assistant.

Return classify_intent with:
- intent: in_scope, needs_clarification, off_topic, or harmful
- reason: brief internal rationale
- confidence: 0 to 1
- missing: geography, measure, vintage, generic, or null

in_scope: US population or demographic questions answerable from ACS block-group data.
needs_clarification: plausible census question missing geography, measure, or vintage.
off_topic: unrelated requests (poems, coding help, non-US geography, general knowledge).
harmful: personal data requests, discriminatory framing, or dangerous instructions.
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
                        "enum": ["in_scope", "needs_clarification", "off_topic", "harmful"],
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
        if intent not in {"in_scope", "needs_clarification", "off_topic", "harmful"}:
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
