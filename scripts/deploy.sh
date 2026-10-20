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
: "${GCP_ARTIFACT_REPO:?GCP_ARTIFACT_REPO is required}"
: "${GCP_SERVICE_NAME:?GCP_SERVICE_NAME is required}"
: "${SNOWFLAKE_ACCOUNT:?SNOWFLAKE_ACCOUNT is required}"
: "${SNOWFLAKE_USER:?SNOWFLAKE_USER is required}"
: "${SNOWFLAKE_ROLE:?SNOWFLAKE_ROLE is required}"
: "${SNOWFLAKE_WAREHOUSE:?SNOWFLAKE_WAREHOUSE is required}"
: "${SNOWFLAKE_DATABASE:?SNOWFLAKE_DATABASE is required}"

# shellcheck disable=SC1091
source "$ROOT_DIR/deploy/cloudrun.env"

SECRET_SNOWFLAKE_PRIVATE_KEY="${SECRET_SNOWFLAKE_PRIVATE_KEY:-miniflake-snowflake-private-key}"
SECRET_ANTHROPIC_API_KEY="${SECRET_ANTHROPIC_API_KEY:-miniflake-anthropic-api-key}"
SECRET_AUTH_SIGNING_SECRET="${SECRET_AUTH_SIGNING_SECRET:-miniflake-auth-signing-secret}"
SECRET_DEMO_PASSPHRASE="${SECRET_DEMO_PASSPHRASE:-miniflake-demo-passphrase}"

RESPONSE_BUDGET_SECONDS="${RESPONSE_BUDGET_SECONDS:-60}"
if (( CLOUD_RUN_REQUEST_TIMEOUT <= RESPONSE_BUDGET_SECONDS )); then
  echo "CLOUD_RUN_REQUEST_TIMEOUT must exceed RESPONSE_BUDGET_SECONDS (${RESPONSE_BUDGET_SECONDS})" >&2
  exit 1
fi

CPU_FLAGS=()
if [[ "${CLOUD_RUN_CPU_ALWAYS_ALLOCATED}" == "true" ]]; then
  CPU_FLAGS=(--cpu-boost --no-cpu-throttling)
else
  CPU_FLAGS=(--no-cpu-boost --cpu-throttling)
fi

IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE_URI="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT}/${GCP_ARTIFACT_REPO}/${GCP_SERVICE_NAME}:${IMAGE_TAG}"

echo "Ensuring Artifact Registry repository exists..."
if ! gcloud artifacts repositories describe "$GCP_ARTIFACT_REPO" \
  --location="$GCP_REGION" \
  --project="$GCP_PROJECT" &>/dev/null; then
  gcloud artifacts repositories create "$GCP_ARTIFACT_REPO" \
    --repository-format=docker \
    --location="$GCP_REGION" \
    --project="$GCP_PROJECT"
fi

echo "Configuring Docker auth..."
gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet

echo "Building image: $IMAGE_URI"
docker build -t "$IMAGE_URI" "$ROOT_DIR"

echo "Pushing image..."
docker push "$IMAGE_URI"

ENV_VARS="APP_NAME=${APP_NAME:-miniflake}"
ENV_VARS+=",ENVIRONMENT=production"
ENV_VARS+=",LOG_LEVEL=${LOG_LEVEL:-INFO}"
ENV_VARS+=",LOG_FORMAT=${LOG_FORMAT:-json}"
ENV_VARS+=",HEALTH_VERSION=${HEALTH_VERSION:-0.1.0}"
ENV_VARS+=",SNOWFLAKE_ACCOUNT=${SNOWFLAKE_ACCOUNT}"
ENV_VARS+=",SNOWFLAKE_USER=${SNOWFLAKE_USER}"
ENV_VARS+=",SNOWFLAKE_ROLE=${SNOWFLAKE_ROLE}"
ENV_VARS+=",SNOWFLAKE_WAREHOUSE=${SNOWFLAKE_WAREHOUSE}"
ENV_VARS+=",SNOWFLAKE_DATABASE=${SNOWFLAKE_DATABASE}"
ENV_VARS+=",SNOWFLAKE_SCHEMA=${SNOWFLAKE_SCHEMA:-PUBLIC}"
ENV_VARS+=",SESSION_COOKIE_SECURE=true"
ENV_VARS+=",DEMO_AUTH_ENABLED=true"
ENV_VARS+=",RESPONSE_BUDGET_SECONDS=${RESPONSE_BUDGET_SECONDS}"
ENV_VARS+=",WARMUP_ENABLED=${WARMUP_ENABLED:-true}"

SECRETS="SNOWFLAKE_PRIVATE_KEY=${SECRET_SNOWFLAKE_PRIVATE_KEY}:latest"
SECRETS+=",ANTHROPIC_API_KEY=${SECRET_ANTHROPIC_API_KEY}:latest"
SECRETS+=",AUTH_SIGNING_SECRET=${SECRET_AUTH_SIGNING_SECRET}:latest"
SECRETS+=",DEMO_PASSPHRASE=${SECRET_DEMO_PASSPHRASE}:latest"

echo "Deploying to Cloud Run..."
gcloud run deploy "$GCP_SERVICE_NAME" \
  --image="$IMAGE_URI" \
  --region="$GCP_REGION" \
  --project="$GCP_PROJECT" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --min-instances="$CLOUD_RUN_MIN_INSTANCES" \
  --max-instances="$CLOUD_RUN_MAX_INSTANCES" \
  --concurrency="$CLOUD_RUN_CONCURRENCY" \
  --timeout="$CLOUD_RUN_REQUEST_TIMEOUT" \
  --cpu="$CLOUD_RUN_CPU" \
  --memory="$CLOUD_RUN_MEMORY" \
  "${CPU_FLAGS[@]}" \
  --startup-probe="initialDelaySeconds=${CLOUD_RUN_STARTUP_INITIAL_DELAY},timeoutSeconds=${CLOUD_RUN_STARTUP_TIMEOUT},periodSeconds=${CLOUD_RUN_STARTUP_PERIOD},failureThreshold=${CLOUD_RUN_STARTUP_FAILURE_THRESHOLD},httpGet.path=/api/health,httpGet.port=8080" \
  --set-env-vars="$ENV_VARS" \
  --set-secrets="$SECRETS"

SERVICE_URL="$(gcloud run services describe "$GCP_SERVICE_NAME" \
  --region="$GCP_REGION" \
  --project="$GCP_PROJECT" \
  --format="value(status.url)")"

echo "Deployed to: $SERVICE_URL"
echo "Health check: ${SERVICE_URL}/api/health"

echo "Running post-deploy smoke test..."
uv run python "$SCRIPT_DIR/smoke_deployed.py" --url "$SERVICE_URL"
