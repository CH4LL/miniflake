# ADR-007: Guardrails

Status: accepted (2026-09-19)

## Context

The agent must refuse off-topic and inappropriate requests, resist instruction injection, and never present numbers that did not come from the data. Each additional check costs latency against the response budget and adds a false-positive risk that would block legitimate questions.

## Options

1. **System prompt instructions only.** Zero latency; but a prompt is advice, not enforcement, and offers nothing to test deterministically.
2. **Single LLM moderation call before the agent.** Catches most off-topic input; adds a call per turn; still leaves the answer itself unchecked.
3. **Layered: deterministic pre-checks, cheap intent classifier, tool-only data access, output grounding check.** Cheapest check first; the data layer is reached only for in-scope input; the answer is verified against tool results after the fact. Highest implementation cost, but each layer is independently testable and the grounding check is the only mechanism that directly enforces the "numbers come from data" requirement.
4. **Third-party guardrail framework.** Adds a dependency and a learning curve for behaviour that here reduces to a pattern list, one classification call and a numeric matcher.

## Decision

Option 3.

- Pre-checks: length and pattern rules maintained in a YAML file, no LLM call.
- Intent classifier: one structured-output call to the cheaper model, classifying into in scope, needs clarification, off topic, harmful, with the last two turns as context. Fails open to the agent on error, logged.
- Tool-only data access: the model cannot obtain data except through typed tools (ADR-004).
- Output grounding check: every numeric token in the answer must match a value in the tool results, allowing displayed-precision rounding and simple derived percentages. Failure replaces the text with a templated explanation while preserving provenance.
- Refusal and clarification texts are templates in a YAML file.

## Consequences

- One extra LLM call per turn for classification; budgeted in the loop's time accounting.
- The grounding check can produce false negatives for legitimate derived figures the matcher does not recognise; these are surfaced as "could not ground" rather than as wrong answers, which is the preferred failure direction. Matcher rules are tuned in S8 from eval results.
- The grounding check is the last cut candidate; if cut, the reflection must state that grounding relies on tool-only access and the prompt alone.
