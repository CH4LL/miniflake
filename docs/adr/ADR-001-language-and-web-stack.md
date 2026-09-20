# ADR-001: Language and web stack

Status: accepted

## Context

The project requires a web-accessible chat agent built in 24 hours, which will later be extended with AI tools and whose architecture has to hold up to scrutiny. The author's fluency and the ease with which a stranger can navigate the code matter as much as raw delivery speed. The stack also has to make protocol-based boundaries (fake LLM, fake repository) natural.

## Options

1. **Python with FastAPI, static vanilla-JS page served by the same process.** Mature Snowflake and Anthropic SDKs, pydantic for schemas that double as LLM tool definitions, `TestClient` for end-to-end tests without a browser, one container to deploy.
2. **Python with Streamlit or Chainlit.** Fastest visible result; but the UI framework owns the process and the request lifecycle, module boundaries blur into callbacks, testing the request path requires framework-specific harnesses, and per-session state semantics are framework-defined.
3. **TypeScript with Next.js.** Strong UI story; SDKs exist for both Snowflake and Anthropic; but the author's live-coding fluency is higher in Python and the Snowflake Node driver is less commonly used, raising the risk of losing time on connection details.
4. **Python FastAPI backend with a separate React/Vite frontend.** Best UI polish; two build systems, CORS, and a second deploy artefact for a chat page whose UI complexity is low.

## Decision

Option 1. Python 3.12, FastAPI, uvicorn, pydantic v2, pydantic-settings, `uv` for dependency management, ruff, pytest. A single container serves the API and a static page.

## Consequences

- Tool schemas are generated from pydantic models; the same models validate LLM tool inputs at runtime.
- End-to-end tests run in-process against the FastAPI app with fakes injected through the app factory.
- The UI is intentionally plain; polish is a cut candidate, not a foundation.
- No frontend build step; any change to the page is a file edit.
