from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.config import Settings
from app.conversation.store import Conversation
from app.guardrails.classifier import IntentClassifier, render_context
from app.guardrails.grounding import check_grounding
from app.guardrails.prechecks import load_patterns, match_patterns
from app.guardrails.types import GuardrailDecision, IntentDecision

TEMPLATES_PATH = Path(__file__).resolve().parent / "templates.yaml"


def load_templates(path: Path | None = None) -> dict[str, str]:
    templates_path = path or TEMPLATES_PATH
    raw = yaml.safe_load(templates_path.read_text(encoding="utf-8"))
    return {key: str(value).strip() for key, value in raw.items()}


class GuardrailPipeline:
    def __init__(
        self,
        settings: Settings,
        classifier: IntentClassifier,
        *,
        patterns: dict[str, list[str]] | None = None,
        templates: dict[str, str] | None = None,
    ) -> None:
        self._settings = settings
        self._classifier = classifier
        self._patterns = patterns or load_patterns()
        self._templates = templates or load_templates()

    def before_agent(self, conversation: Conversation, message: str) -> GuardrailDecision | None:
        precheck = match_patterns(message, self._patterns)
        if precheck.category is not None:
            return GuardrailDecision(
                outcome="refuse",
                text=self._templates[precheck.category],
            )

        context_excerpt = render_context(
            conversation.messages,
            self._settings.guardrail_classifier_context_turns,
        )
        decision = self._classifier.classify(message, context_excerpt)
        return self._decision_from_intent(decision)

    def check_answer(
        self,
        text: str,
        payloads: list[dict[str, Any]],
    ) -> GuardrailDecision | None:
        verdict = check_grounding(text, payloads, self._settings)
        if verdict.grounded:
            return None
        return GuardrailDecision(
            outcome="unanswerable",
            text=self._templates["ungrounded_answer"],
        )

    def _decision_from_intent(self, decision: IntentDecision) -> GuardrailDecision | None:
        if decision.intent == "off_topic":
            return GuardrailDecision(outcome="refuse", text=self._templates["off_topic"])
        if decision.intent == "harmful":
            return GuardrailDecision(outcome="refuse", text=self._templates["harmful"])
        if decision.intent == "needs_clarification":
            missing = decision.missing or "generic"
            template_key = f"needs_clarification_{missing}"
            return GuardrailDecision(
                outcome="clarify",
                text=self._templates.get(
                    template_key, self._templates["needs_clarification_generic"]
                ),
            )
        return None
