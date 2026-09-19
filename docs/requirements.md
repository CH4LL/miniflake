# Requirements

## 1. Goal

Build a production-quality, interactive chat agent that answers natural-language questions about the US population, grounded in the US Open Census dataset from the Snowflake Marketplace. The agent is served through a web interface reachable on the public internet. The work is time-boxed to 24 hours, so open technical decisions have to be made quickly, and every choice must be explainable and defensible.

## 2. Data source

- Required: US Open Census dataset from the Snowflake Marketplace, accessed through a free Snowflake trial account.
- Free choice: how the data is queried, transformed, and served.
- The solution does not need to be built or hosted on the Snowflake platform.

## 3. Core functionality

| ID | Requirement |
| :--- | :--- |
| CF-1 | Interactive, chat-based agent that answers natural-language questions grounded in the Census dataset. |
| CF-2 | Web-based interface accessible on the public internet; no local setup required to evaluate. Authentication is acceptable if demo credentials are shared with reviewers. |
| CF-3 | Conversation context is preserved across multiple turns. |
| CF-4 | Complete responses are returned within 60 seconds under normal conditions. |
| CF-5 | Guardrails prevent off-topic or inappropriate responses. |

## 4. Production quality bar

The code should meet the standard applied to code handed off to a customer.

| ID | Requirement |
| :--- | :--- |
| PQ-1 | Graceful degradation: when a question cannot be answered from the available data, the agent says so clearly and helpfully. No hallucinated answers, empty responses, or unhandled errors. |
| PQ-2 | Ambiguous, partially matching, conflicting or underspecified, and reasonable-but-unanswerable queries are recognised and handled deliberately. |
| PQ-3 | Meaningful tests that give confidence in the implementation, with a testing strategy whose scope and tradeoffs can be explained. |
| PQ-4 | README lets a new engineer understand the architecture and lets reviewers evaluate the running demo. |
| PQ-5 | Answers come from the data, never from model memory; provenance (what data backed the answer) is visible. |
| PQ-6 | Codebase is easy to extend: small modules, clear tool/agent boundaries, one obvious place to add a new data source or tool. |
| PQ-7 | Every architectural choice included is one that can be justified; anything that cannot be justified is left out. |

## 5. Open decisions to record

These choices were left open. Each must be documented in the README and, where alternatives were weighed, in an ADR under `docs/` and in `docs/decision_log.md`:

- Hosting and deployment target for the public web interface.
- LLM provider and model.
- Query strategy over the Census data (e.g. text-to-SQL against Snowflake vs. pre-aggregated or cached views).
- Authentication for the demo, if any.
- Guardrail mechanism for off-topic and inappropriate requests.
- Conversation state storage and context management.
- Testing strategy and its tradeoffs.
