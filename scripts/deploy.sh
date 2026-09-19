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

echo "Deploying to Cloud Run..."
gcloud run deploy "$GCP_SERVICE_NAME" \
  --image="$IMAGE_URI" \
  --region="$GCP_REGION" \
  --project="$GCP_PROJECT" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --set-env-vars="APP_NAME=${APP_NAME:-miniflake},ENVIRONMENT=production,LOG_LEVEL=${LOG_LEVEL:-INFO},HEALTH_VERSION=${HEALTH_VERSION:-0.1.0},SNOWFLAKE_ACCOUNT=placeholder,SNOWFLAKE_USER=placeholder,SNOWFLAKE_ROLE=placeholder,SNOWFLAKE_WAREHOUSE=placeholder,SNOWFLAKE_DATABASE=placeholder,SNOWFLAKE_SCHEMA=PUBLIC,SNOWFLAKE_PRIVATE_KEY_PATH=/dev/null"

SERVICE_URL=$(gcloud run services describe "$GCP_SERVICE_NAME" \
  --region="$GCP_REGION" \
  --project="$GCP_PROJECT" \
  --format="value(status.url)")

echo "Deployed to: $SERVICE_URL"
echo "Health check: ${SERVICE_URL}/api/health"
