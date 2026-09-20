# ADR-002: LLM provider

Status: accepted

## Context

The agent needs a model that reliably selects typed tools with schema-validated arguments, produces structured output for the guardrail classifier, and answers within a strict response budget. The author's available credentials at planning time were a Cursor API key (Cursor Agent CLI, Cloud Agent API, Cursor SDK) and a willingness to obtain an Anthropic key.

## Options

1. **Cursor SDK as the inference backend.** Already paid for. Investigated and rejected: the SDK runs a coding agent (local executor or cloud VM) equipped with file and shell tools; there is no plain chat-completions surface, custom tools are only available through MCP servers, there is no strict tool-schema or structured-output control, the product is in public beta, and per-turn latency is that of an agent run rather than a single completion. Exposing a coding agent behind a public chat page is also a prompt-injection hazard. "A coding agent as my chat model" is not defensible under interrogation.
2. **Snowflake Cortex LLM functions.** Keeps everything on one platform and needs no external key; but trial accounts are capped to a small daily credit allowance for Cortex AI functions, model availability varies by region, the tool-use path (Cortex Agents) is a heavier integration than a direct API, and it would couple the LLM to the data platform, weakening the "swap the data source" extension story.
3. **Anthropic Messages API.** Strict tool-use schemas, structured outputs with JSON Schema, a fast mid-tier model for the agent and a cheaper model for classification, well-documented Python SDK. Requires obtaining a key; projected spend for development and evaluation is a few dollars.
4. **OpenAI.** Equivalent capability; the author had no key and no preference, so it offers no advantage over option 3.

## Decision

Option 3. The agent uses a Sonnet-tier model; the guardrail classifier uses a Haiku-tier model. Concrete model identifiers, effort settings, token limits and timeouts are configuration values. The provider is accessed only through the `LLMClient` protocol in `app/llm/`, with an Anthropic implementation and a scripted fake.

Cursor remains the coding tool used to build the project.

## Consequences

- One external credential to manage in Secret Manager.
- The protocol boundary keeps a second provider a one-file addition.
- Tool-use system prompt overhead and per-call latency are known and budgeted in the agent loop.
- If the Anthropic key is unavailable at S3, the fallback is option 4 behind the same protocol; option 1 is not a fallback.
