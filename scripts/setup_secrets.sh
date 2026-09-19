#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

: "${GCP_PROJECT:?GCP_PROJECT is required}"
: "${GCP_REGION:?GCP_REGION is required}"

SECRET_SNOWFLAKE_PRIVATE_KEY="${SECRET_SNOWFLAKE_PRIVATE_KEY:-miniflake-snowflake-private-key}"
SECRET_ANTHROPIC_API_KEY="${SECRET_ANTHROPIC_API_KEY:-miniflake-anthropic-api-key}"
SECRET_AUTH_SIGNING_SECRET="${SECRET_AUTH_SIGNING_SECRET:-miniflake-auth-signing-secret}"
SECRET_DEMO_PASSPHRASE="${SECRET_DEMO_PASSPHRASE:-miniflake-demo-passphrase}"

upsert_secret() {
  local name="$1"
  local value="$2"
  if gcloud secrets describe "$name" --project="$GCP_PROJECT" &>/dev/null; then
    printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=- --project="$GCP_PROJECT"
    echo "Updated secret: $name"
  else
    printf '%s' "$value" | gcloud secrets create "$name" --data-file=- --project="$GCP_PROJECT"
    echo "Created secret: $name"
  fi
}

resolve_snowflake_private_key() {
  if [[ -n "${SNOWFLAKE_PRIVATE_KEY:-}" ]]; then
    printf '%s' "$SNOWFLAKE_PRIVATE_KEY"
    return
  fi
  if [[ -n "${SNOWFLAKE_PRIVATE_KEY_PATH:-}" ]]; then
    cat "$SNOWFLAKE_PRIVATE_KEY_PATH"
    return
  fi
  echo "SNOWFLAKE_PRIVATE_KEY or SNOWFLAKE_PRIVATE_KEY_PATH is required" >&2
  exit 1
}

: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY is required}"
: "${AUTH_SIGNING_SECRET:?AUTH_SIGNING_SECRET is required}"
: "${DEMO_PASSPHRASE:?DEMO_PASSPHRASE is required}"

SNOWFLAKE_KEY="$(resolve_snowflake_private_key)"
upsert_secret "$SECRET_SNOWFLAKE_PRIVATE_KEY" "$SNOWFLAKE_KEY"
upsert_secret "$SECRET_ANTHROPIC_API_KEY" "$ANTHROPIC_API_KEY"
upsert_secret "$SECRET_AUTH_SIGNING_SECRET" "$AUTH_SIGNING_SECRET"
upsert_secret "$SECRET_DEMO_PASSPHRASE" "$DEMO_PASSPHRASE"

PROJECT_NUMBER="$(gcloud projects describe "$GCP_PROJECT" --format='value(projectNumber)')"
RUNTIME_SA="${GCP_RUN_SERVICE_ACCOUNT:-${PROJECT_NUMBER}-compute@developer.gserviceaccount.com}"

for secret in \
  "$SECRET_SNOWFLAKE_PRIVATE_KEY" \
  "$SECRET_ANTHROPIC_API_KEY" \
  "$SECRET_AUTH_SIGNING_SECRET" \
  "$SECRET_DEMO_PASSPHRASE"; do
  gcloud secrets add-iam-policy-binding "$secret" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="$GCP_PROJECT" \
    --quiet
  echo "Granted secretAccessor on $secret to ${RUNTIME_SA}"
done

echo "Secret Manager bootstrap complete."
