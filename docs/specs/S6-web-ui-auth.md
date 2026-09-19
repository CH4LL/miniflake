# S6: Web UI and demo auth

Status: see [roadmap.md](../roadmap.md). Estimate: 2 h. Depends on S4 (S5 preferred).

## Goal

A minimal, dependable chat page that shows answers with their provenance, plus a passphrase gate so the public demo is reachable only by reviewers who hold the credentials.

## Scope

1. Static page served by FastAPI at `/`: message list, input box, send button, loading indicator, error banner, "New conversation" button.
2. Per assistant message: outcome badge (answer, clarification, unanswerable, refused, error) and a collapsible provenance panel listing each tool call, the variable and geography names, year, measurement period, and the SQL with parameters.
3. `POST /api/login` exchanging the passphrase for a signed, HTTP-only cookie; middleware requiring it for `/api/chat` and `/api/conversations/*`; `/api/health` stays open.
4. Login form shown when the cookie is missing or invalid.

## Out of scope

Build tooling, frameworks, streaming, mobile-specific layouts beyond responsive width, user accounts.

## Behaviour

- Vanilla JS with `fetch`; no bundler. Keyboard: Enter sends, Shift+Enter inserts a newline.
- The page disables input while a request is in flight and shows elapsed seconds so the user understands longer waits.
- API errors render in the banner with the request id for support.
- Cookie signing uses an HMAC secret from configuration; cookie lifetime and passphrase come from configuration. Constant-time comparison for the passphrase. Failed logins are logged with the client address.
- When the demo auth is disabled by configuration (local development), the middleware is a no-op.

## Acceptance criteria

- Given no cookie, when `POST /api/chat` is called, then the response is 401 with code `unauthorized`.
- Given a wrong passphrase, when `POST /api/login` is called, then the response is 401 and no cookie is set.
- Given the correct passphrase, then a signed cookie is set and `POST /api/chat` succeeds.
- Given a tampered cookie, then `POST /api/chat` returns 401.
- Given the page is loaded in a browser against a local server with fakes, when two messages are sent, then two assistant messages render, the second reflects the follow-up, and the provenance panel expands to show tool calls.
- Given an API error response, then the banner shows the message and request id and the input is re-enabled.

## Tests to write first

1. `tests/unit/api/test_auth.py`: cookie signing and verification, tamper detection, constant-time comparison wrapper.
2. `tests/e2e/test_auth_api.py`: login and protected route behaviour.
3. `tests/e2e/test_ui_smoke.py`: Playwright (opt-in via `RUN_BROWSER_TESTS=1`) two-turn conversation and provenance expansion against the app with fakes.

## Files

- `web/index.html`, `web/app.js`, `web/styles.css`
- `app/api/auth.py`, `app/api/static.py`
- `app/main.py` wiring

## Documentation updates at stage end

`USER-GUIDE.md` (using the chat page, reading provenance, logging in), `ARCHITECTURE.md` (Web UI and auth rows), `CHANGELOG.md`, `docs/roadmap.md`.
