#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export ARTIFACT_URI="${ARTIFACT_URI:-file://$(pwd)/artifacts}"
uv run python -m iris.train
