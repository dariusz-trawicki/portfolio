#!/usr/bin/env bash
# Trains a fresh model and uploads it to the fake-gcs-server running on KIND.
# Requires: a KIND cluster with the iris-local namespace and a running fake-gcs (see local/fake-gcs.yaml).
set -euo pipefail
cd "$(dirname "$0")/.."

NAMESPACE="iris-local"
BUCKET="iris-models"
LOCAL_PORT="4443"
FAKE_GCS_URL="http://localhost:${LOCAL_PORT}"

cleanup() {
  if [[ -n "${PF_PID:-}" ]]; then
    kill "$PF_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "==> Checking fake-gcs availability in namespace ${NAMESPACE}"
kubectl -n "$NAMESPACE" get deploy/fake-gcs >/dev/null 2>&1 || {
  echo "fake-gcs deployment not found. Run first: kubectl apply -f ../iris-mlops-config/local/fake-gcs.yaml"
  exit 1
}
kubectl -n "$NAMESPACE" wait --for=condition=available deploy/fake-gcs --timeout=60s

echo "==> Port-forwarding to fake-gcs on port ${LOCAL_PORT}"
kubectl -n "$NAMESPACE" port-forward svc/fake-gcs "${LOCAL_PORT}:4443" >/dev/null 2>&1 &
PF_PID=$!

# wait until the port actually responds, instead of a fixed "sleep 2"
for _ in $(seq 1 20); do
  curl -s -o /dev/null "${FAKE_GCS_URL}/storage/v1/b" && break
  sleep 0.5
done

echo "==> Training a fresh model"
export ARTIFACT_URI="file://$(pwd)/artifacts"
rm -rf artifacts/
uv run python -m iris.train

VERSION=$(ls artifacts/)
echo "==> Model version: ${VERSION}"

echo "==> Ensuring bucket ${BUCKET} exists"
curl -s -X POST "${FAKE_GCS_URL}/storage/v1/b?project=local" \
  -H 'content-type: application/json' \
  -d "{\"name\":\"${BUCKET}\"}" >/dev/null || true

echo "==> Uploading artifacts"
for f in artifacts/"$VERSION"/*; do
  name=$(basename "$f")
  curl -s -X POST \
    "${FAKE_GCS_URL}/upload/storage/v1/b/${BUCKET}/o?uploadType=media&name=models/${VERSION}/${name}" \
    -H 'content-type: application/octet-stream' \
    --data-binary @"$f" >/dev/null
  echo "   - ${name}"
done

echo ""
echo "==> Done. MODEL_URI to use in the ConfigMap:"
echo "    gs://${BUCKET}/models/${VERSION}/"
