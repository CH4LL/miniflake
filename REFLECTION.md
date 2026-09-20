# Reflection

Covers the development process, key decisions, what was left out or would change, known failure modes, and testing. Where a claim can be checked, it points at a file, an ADR, a decision log entry or an eval item id.

## Development process

The project was built with heavy use of AI coding agents, as architects, planners and implementers, inside Cursor. My own time went into three things: shaping the architectural guidance the agents worked from, catching mistakes and misconceptions when I saw them, and writing or rewriting the documents that matter most

### Shape of the 24 hours

Git history runs from 06:08 on day one to 02:46 on day two, about 20.5 hours of recorded work before the final documentation pass.

| Window | What happened |
| :--- | :--- |
| Hours 0 to 2 | No product code. Requirements written down ([docs/requirements.md](docs/requirements.md)), then architecture, a ten-stage roadmap, one spec per stage, eight ADRs and the first golden question set. The dataset default was reversed inside this window once I read the requirements as naming the SafeGraph listing explicitly, which agents wanted to override as inadequate (ADR-003). |
| Hours 2 to 9 | S0 to S7, one commit per stage: Snowflake foundations and a Cloud Run skeleton, data layer, typed tools, agent loop, conversation and API, guardrails, web UI with passphrase auth, hardened deployment. Each stage was implemented against its spec with tests written first. |
| Hours 9 to 21 | S8, evaluation and hardening. The first eval run against the deployed service passed 29 of 51 items. The plan to run, fix and rerun against the live service was abandoned after one iteration as too slow and too expensive; failures were triaged by cause, deterministic ones were fixed against fakes, and one final live run was taken as the measurement: 51 of 53 ([evals/reports/20260920T004303Z.md](evals/reports/20260920T004303Z.md)). |
| Final hours | Documentation, this reflection, and the restructuring of the decision log and ADRs so a reviewer can follow the reasoning without reading chat history. |

### How the agents were steered

The working method is in [docs/agent-workflow.md](docs/agent-workflow.md) and `.cursorrules`. An agent picking up work reads the roadmap, opens the current stage's spec, writes the tests the spec lists, implements, and is not allowed to start the next stage. When the spec turned out to be wrong, the spec was edited before the code. Every deviation and every rejected alternative went into [docs/decision_log.md](docs/decision_log.md) as it happened rather than being reconstructed afterwards.

This constrained the generated code in ways I wanted: modules had to satisfy tests that already described outcomes such as `Ambiguous`, `NotFound` and `PeriodUnavailable`; adjustable values were pushed into `app/config.py` rather than code or docs; a later session could pick up from the roadmap instead of the previous conversation.

This applied to the main implementations, since bugfixing and ad-hoc adjustments which did not have the roadmap or spec inclusions, relied on flexible context, though cursorrules always applies.

Where I overruled the agents: the Cursor SDK was proposed as the chat model because a key was already paid for, and rejected after reading its surface (it is a coding-agent runtime, not a completions API (ADR-002)); Preference for a larger dataset rather than the one provided, due to it not being able to serve all types of content (overruled, as requirements were specific as to what data can be used (ADR-003)); A post-answer numeric grounding check that the agents built to enforce "numbers come from data" was removed when it blocked a legitimate follow-up comparing a 2020 figure with the previous turn's 2019 figure (ADR-007 amendment). The S8 plan of running live evals as the development loop was rewritten in place. The composer's outcome labels were originally inferred from phrases in the model's text; six of the baseline eval failures were that, and it was replaced by typed signals (ADR-011).

### Tooling and cost

Cursor was the harness throughout. Different models did different jobs: the largest architectural decisions and overhauls were planned with the most capable model available to me, most stage planning with a strong reasoning model, most implementation with a cheap, fast model that proved good at following a spec, and most debugging with a fourth model. Spend on coding agents was about $30. The application itself cost far less to run: the GCP free tier, a Snowflake trial, and about $5 of Anthropic usage across development and evaluation.

The budget was a real constraint. As a private individual there is a limit to what I will spend on agents for a take-home task, and I cut planning depth accordingly; in an organisation, spending several times that on the most capable model architecting every stage is cheap against a day of an engineer's time. The tradeoff shows in the codebase: some generated modules and documents are more verbose than I would write by hand, and some decisions were reviewed at different precision levels.

## Key architectural decisions

Each of these has an ADR under [docs/adr/](docs/adr/) with the alternatives weighed. The ones that most shaped the result, with the tradeoff accepted:

- **Typed semantic tools instead of text-to-SQL** (ADR-004). The model selects one of six tools and fills typed parameters; SQL is templated and parametrised inside the data layer, and every "cannot answer" is a typed result rather than a failed query. Provenance is exact and the whole path is testable with a fake repository and a scripted LLM. The cost is expressiveness: a question the six tools cannot express is declared unanswerable rather than attempted. For a 24-hour build handed to a customer I prefer enumerable failure modes over a free-form SQL surface whose failures I cannot list.
- **The SafeGraph listing only, with counts-only rollups** (ADR-003, ADR-004). The requirements name the listing; it carries block-group grain with no place or metro mapping. Count fields are summed to county, state and nation. Medians and rates at those levels are refused rather than approximated, because a sum of block-group medians is not a median. This makes "median household income in Cook County" unanswerable, which is honest, but the prefferred choice in my opinion, when we have to choose between using available data, and solving required use-cases.
- **Anthropic behind an `LLMClient` protocol; a Sonnet-tier model for the agent with low-effort adaptive thinking, a Haiku-tier model for the intent classifier** (ADR-002). Strict tool schemas and structured output fit the typed-tool design; the cheap classifier keeps the guardrail call fast. Snowflake Cortex was rejected for for coupling the LLM to the data platform. Model identifiers and effort are configuration.
- **Full per-turn transcripts as conversation context** (ADR-009). CF-3 says context must be preserved without saying at which precision, so I assumed full. I stored everything the provider saw (tool calls and results included) plus a small extracted `ResolvedContext`, so no follow-up is ruled out by a choice the code made about what mattered. The cost is tokens per turn which does add up, especially in production. I didn't see a meaningful reason to keep the entire context, so I would have liked to ask a clarifying question to stakeholders, but in absence of that, better to stick to the requirements than ruthlessly optimize I think.
- **60 seconds as the normal-conditions target, not the hard kill** (ADR-010). Evals score against 60 seconds and the system prompt tells the model the budget; agent, API and Cloud Run timeouts sit above it so a hard ranking finishes instead of being cut, and requests can go past it in normal usage in rare complex cases, though per-turn iteration and catalog-search caps bound model thrash regardless of prompt compliance. 60 seconds was stated as required "under normal conditions", but that seems like system intent, i.e evals, not a technical one, where an upper system breaks due to lack of an answer. Another place where I would have asked a question.
- **Outcome labels from typed signals, never from prose** (ADR-011). Whether a turn is an answer, a clarification or an honest refusal is derived from tool traces and classifier intent, so a change in the model's wording cannot move a label or the eval gate.
- **Layered guardrails with the data path as the last layer** (ADR-007). Regex pre-checks, then a cheap classifier, then tool-only data access. Off-topic and harmful input never reaches Snowflake. The classifier fails open to the agent on error, which I chose over failing closed so a provider blip does not refuse every question.
- **In-memory conversations on one warm Cloud Run instance, passphrase auth** (ADR-005, ADR-006). Simple for reviews and development, likely lacking for production, but not too difficult to extend.
- **Protocol fakes, contract tests, opt-in live suites, evals as a measurement** (ADR-008). CI never needs credentials; the fake repository is held to the real one by shared contract tests.

## What I deliberately left out

- **Observability beyond logs.** Structured JSON logging with request id, latency, tool calls and token usage exists and was enough to debug the agent locally and on Cloud Run. Metrics, alarms and dashboards were skipped: not required, expected traffic is tiny, and sensible thresholds need traffic I do not have. A production release would need them.
- **A rigorous evaluation suite.** There is a 53-item golden set with typed scoring, offline re-scoring and a self-tested runner, but no LLM grader and no expert-graded reference answers. Judging answer quality and style, not only outcome class and value, would need both, plus time and credits for repeated grading runs. The current set measures whether the agent does the right kind of thing the best I could make it do so, not how well it says it.
- **Place and metro geographies.** The optional stage that would have added them from a second listing was cut (decision log `Cut S10 public data supplement`). City questions are answered with an explanation of the supported levels.
- **Persistence and horizontal scaling.** One instance, memory-held conversations. Sessions are lost on redeploy, which is sufficient at this scale, but otherwise imperfect.
- **Front-end polish and streaming.** A plain vanilla-JS page with a provenance panel; no streaming, so the user sees a spinner for the full turn.
- **A constrained free-SQL tool** for the long tail the six tools cannot express. Listed as an extension, not built, because the validator has to be right and I did not have time to make it so.
- **Reconciling the curated variable catalogue against the share.** The catalogue lists series (poverty, housing, health insurance, commuting) for which the marketplace metadata returns no fields, so the system prompt advertises topics the tools cannot serve. Found in the final live run; fixing it needs a live metadata query at build time. I wasn't sure how to fix it in time, so I focused on reliable improvements elsewhere.

## What I would do differently with more time

- **Documentation written for readers, not by stage.** Most documents were produced by agents on a best-effort basis and it shows: style fixations, over-citation, repetition across files, and simply too many documents for a repository of this size. I addressed the highest-value ones by hand at the end. With more time I would cut the document count in half and rewrite the rest in one voice.
- **Guardrails designed by hand.** The pre-checks, classifier prompt and templates were designed by agents to fit the general shape of "a census agent". They are generic, sometimes rigid, and will not catch everything, allowing things to pass through to the agent and rely on the tool-only data path. If one component should be redesigned with careful human oversight before a production release, it is this one.
- **A tighter agentic workflow.** The volume of work and the number of technologies meant leaving agents a lot of freedom in technology selection, planning and implementation. I could not check every line or every sentence of a plan and still finish, so I relied on further agent passes to verify and fix. It worked well enough, and the spec-first structure is what made it work, but a second engineer or another day would have gone into review rather than features.
- **Terminal pseudo-tools for outcomes.** Letting the model declare `unanswerable` or `ask_clarification` explicitly is a cleaner design than inferring the label from traces, and would fix the one known labelling gap (a clarifying question the model writes without any tool returning `ambiguous` is labelled `unanswerable`). It was dropped because every scripted-fake test would need the extra call and that could not be done and verified in the time left (ADR-011).

## Edge cases and failure modes identified but not fully addressed

Observed in the eval reports, the local logs, or while writing tests. Cited by golden-set id where one exists.

- **Clarification standing in for an explanation (AG01, UL02).** An ambiguous place name and a street address both reach the canned "which geography did you mean?" question, because the classifier sees a missing geography slot where the real answer is that the dataset has no such grain. Not wrong for the user, but weaker than naming the limit. These are the two remaining failures in the final report and are accepted with reasons in [docs/testing-strategy.md](docs/testing-strategy.md).
- **A catalogue that promises more than the share holds (L07).** Poverty queries spent their search budget and then reported a search limit rather than a dataset limit, because the curated spec lists the series. The prompt and the catalogue come from the same fixture, which made the mismatch invisible until an eval item expected an answer from it.
- **Silent level substitution (L06).** Asked about a city, the model may pick the containing county and answer. The prompt forbids switching levels without saying so, and the item currently passes, but nothing deterministic prevents it; only the answer text distinguishes an honest reformulation from a silent substitution.
- **Ambiguous place names (AG01, AG03).** "Orange County" exists in eight states in the fixtures alone. `find_geography` returns candidates, but the model sometimes picks one when the user's hint does not match a state name. Nicknames such as "the Bay Area" are not resolved.
- **ACS 5-year versus decennial.** "2020 population" returns the 2020 ACS 5-year estimate, which is a 2016 to 2020 window and differs from the 2020 count. The tool description carries the note; the answer text does not always repeat it.
- **Model-written clarifications.** A "which Washington?" the model writes on its own, with no tool having returned `ambiguous`, is labelled `unanswerable`. The classifier is expected to catch missing geography first; when it does not, the badge is wrong even though the reply is fine.
- **Figures without this-turn provenance.** With the numeric grounding check removed, a model that quotes a prior turn's figure, or invents one, is not blocked at runtime. Eval value checks are the detection. The prompt discipline held in the final run, but it is discipline, not enforcement.
- **Classifier fails open.** A run of provider errors would let off-topic questions reach the agent, where the system prompt and the absence of any non-census tool are the remaining defence.
- **Injection coverage.** The pattern list covers the golden-set variants (I01 to I03); paraphrases in another language or instructions split across turns are not matched.
- **Cold warehouse and single instance.** A resumed warehouse adds seconds the harness attributes to the agent; a restart loses every conversation.

## How I approached testing, and what I would add

Everything was built with TDD in mind, i.e test-first. With coding agents involved I consider this the single most effective control: a test written from the spec before the implementation fixes the intended behaviour in a form the agent cannot reinterpret, and a failing test is a clearer correction than a review comment, allowing them to catch and fix mistakes as they go, drastically improving accuracy and speed, while also working as de-facto regression tests for later.

The strategy is ADR-008 and [docs/testing-strategy.md](docs/testing-strategy.md). In outline:

- **Every external dependency behind a protocol with a fake.** `FakeCensusRepository`, `FakeLLM` and the in-memory store let the whole request path run in-process without credentials. `FakeLLM` is scripted per test with the exact tool-call sequence, so each component test reads as a behavioural example.
- **Contract tests keep the fake honest.** The repository suite is parametrised over the fake and the Snowflake implementation; the real one runs only when live tests are enabled. This caught, among other things, the fake and the real search diverging on token matching.
- **Layers.** Unit tests for pure logic; component tests for tools and the agent loop against fakes; end-to-end API tests through FastAPI's `TestClient` covering multi-turn follow-ups, error envelopes, auth and eval-derived guardrail inputs; opt-in live suites; one opt-in Playwright smoke test. The eval runner is itself tested end to end against the app with fakes.
- **Evals as a measurement, not a loop.** 53 golden items over 16 behaviour categories with typed failures (outcome, provenance, value, tool budget, latency). Raw observations are stored in the report, so a scoring-rule change is a free offline re-score instead of a paid rerun. Live runs were taken twice: a baseline (29 of 51) and a final measurement (51 of 53, latency p50 and p95 inside the target).

At the end of the build the default suite is 333 tests, credential-free; 24 more are opt-in live or browser tests.

What is missing, and what I would add first:

- **An LLM grader with expert-graded references** for answer quality and tone, alongside the current outcome and value checks. Without it the suite says nothing about whether an unanswerable reply is actually helpful.
- **Load and soak tests.** The demo is one instance with a concurrency cap; I have no measurement of behaviour under concurrent users or of the in-memory store over hours beyond TTL unit tests.
- **Systematic red-teaming** beyond the injection and harmful categories in the golden set, in particular multilingual and multi-turn attacks.
- **SQL correctness across the whole catalogue.** Templates are tested on representative variables and evals sample value accuracy; a sweep over every series and level against independently computed references is not there.
- **Variance.** A repeated live run to see which passes are stable.
- **Classifier token usage in the API payload**, so the eval cost line covers both models.
