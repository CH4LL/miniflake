from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Intent = Literal["in_scope", "capability", "needs_clarification", "off_topic", "harmful"]
INTENTS: frozenset[str] = frozenset(
    {"in_scope", "capability", "needs_clarification", "off_topic", "harmful"}
)
MissingElement = Literal["geography", "measure", "vintage", "generic"]
GuardrailOutcome = Literal["refuse", "clarify", "unanswerable", "proceed"]
PrecheckCategory = Literal["injection", "sql_execution", "personal_data"]


class PrecheckResult(BaseModel):
    category: PrecheckCategory | None = None


class IntentDecision(BaseModel):
    intent: Intent
    reason: str = ""
    confidence: float = 1.0
    missing: MissingElement | None = None
    failed_open: bool = False


class GuardrailDecision(BaseModel):
    outcome: GuardrailOutcome
    text: str
    ungrounded_answer_allowed: bool = False

    @property
    def short_circuits(self) -> bool:
        return self.outcome != "proceed"
