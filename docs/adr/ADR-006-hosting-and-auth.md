# ADR-006: Hosting and demo authentication

Status: accepted (2026-09-19)

## Context

The demo must be reachable on the public internet with no local setup for reviewers. Authentication is permitted if credentials are supplied. The author has an existing GCP account and operational experience with AWS and GCP; no account with Fly.io, Render or Railway. Setup time counts against the 24-hour budget.

## Options

1. **Google Cloud Run.** Container-based, HTTPS URL out of the box, Secret Manager integration, min-instances setting to keep one warm instance, existing account and tooling. Cold starts are avoided by pinning a minimum instance.
2. **Fly.io / Render / Railway.** Comparable simplicity; each requires account creation, CLI setup and learning the secret model, with no offsetting benefit over option 1 for this workload.
3. **AWS App Runner or ECS.** Familiar to the author but more configuration surface (IAM, VPC defaults, load balancer) for the same outcome.
4. **Streamlit in Snowflake.** Would avoid external hosting; ruled out by ADR-001 (framework owns the process) and by the desire to keep the application platform-independent.

For authentication:

- **None.** Simplest; leaves the LLM and Snowflake spend open to anyone who finds the URL.
- **Shared passphrase exchanged for a signed cookie.** One secret to share out of band; trivial to implement and test; adequate for a review window.
- **Identity-aware proxy or OAuth.** Correct for production; disproportionate here and would force reviewers through account flows.

## Decision

Cloud Run from a Docker image built with `uv`, secrets in Secret Manager, structured JSON logging to Cloud Logging, minimum and maximum instances set to one during the review window, request timeout above the response budget. Demo access through a shared passphrase that sets an HMAC-signed, HTTP-only cookie; the passphrase is shared out of band. The health endpoint stays unauthenticated.

## Consequences

- One instance means no horizontal scaling during the demo; consistent with ADR-005.
- Costs are bounded: an idle warm instance plus per-request LLM and warehouse usage.
- The passphrase gate is not a user model; the README states this and names the production alternative.
- Cloud Run region is chosen near the Snowflake account region to keep query latency low.
