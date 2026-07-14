#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly ENV_FILE="${ENV_FILE:-${SCRIPT_DIR}/.env}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

readonly PROJECT_ID="${PROJECT_ID:-mullan-gmail-com}"
readonly SERVICE_NAME="${SERVICE_NAME:-restaurant-finder}"
readonly REGION="${REGION:-us-central1}"
readonly GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-global}"
readonly GOOGLE_GENAI_USE_VERTEXAI="${GOOGLE_GENAI_USE_VERTEXAI:-TRUE}"
readonly MODEL_NAME="${MODEL_NAME:-gemini-3-flash-preview}"
readonly MEMORY="${MEMORY:-1Gi}"

cd "${SCRIPT_DIR}"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "Required command not found: gcloud" >&2
  exit 1
fi

PROJECT_NUMBER="$(
  gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)'
)"
readonly PROJECT_NUMBER
readonly SERVICE_URL="https://${SERVICE_NAME}-${PROJECT_NUMBER}.${REGION}.run.app"

echo "Enabling Cloud Run build APIs in ${PROJECT_ID}..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  --project "${PROJECT_ID}" \
  --quiet

use_vertex_ai="${GOOGLE_GENAI_USE_VERTEXAI}"
if [[ -n "${GEMINI_API_KEY_SECRET:-}" ]]; then
  use_vertex_ai="FALSE"
fi

if [[ "${use_vertex_ai}" != "TRUE" && -z "${GEMINI_API_KEY_SECRET:-}" ]]; then
  echo "GOOGLE_GENAI_USE_VERTEXAI must be TRUE unless GEMINI_API_KEY_SECRET is set." >&2
  exit 1
fi

deploy_args=(
  run deploy "${SERVICE_NAME}"
  --source .
  --project "${PROJECT_ID}"
  --region "${REGION}"
  --memory "${MEMORY}"
  --allow-unauthenticated
  --set-env-vars
  "AGENT_URL=${SERVICE_URL},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION},GOOGLE_GENAI_USE_VERTEXAI=${use_vertex_ai},MODEL_NAME=${MODEL_NAME}"
  --quiet
)

# To use a Google AI Studio key instead of Vertex AI, point this variable at an
# existing Secret Manager secret whose latest version contains the key.
if [[ -n "${GEMINI_API_KEY_SECRET:-}" ]]; then
  deploy_args+=(--set-secrets "GEMINI_API_KEY=${GEMINI_API_KEY_SECRET}:latest")
fi

echo "Deploying ${SERVICE_NAME} to Cloud Run..."
gcloud "${deploy_args[@]}"

echo "Deployment complete: ${SERVICE_URL}"
