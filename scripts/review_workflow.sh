#!/usr/bin/env bash
# Read an existing W001 report using the original server config/environment.
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo 'Usage: bash scripts/review_workflow.sh JOB_ID ORIGINAL_JOB_COMMIT' >&2
  exit 2
fi
IES_REVIEW_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
IES_ORIGINAL_ROOT="$(cd "$IES_REVIEW_ROOT" && cd "$(git rev-parse --git-common-dir)/.." && pwd -P)"
cd "$IES_ORIGINAL_ROOT"
IES_REMOTE_CONFIG="$PWD/configs/remote.local.yaml"
IES_UV="$(command -v uv || printf '%s' "$PWD/.tools/bin/uv")"
IES_PYTHON="$("$IES_UV" run --locked --no-sync python -c 'import sys; print(sys.executable)')"
cd "$IES_REVIEW_ROOT"
export IES_EXECUTION_CONTEXT=ucsf
export PYTHONPATH="$PWD/src"
export PYTHONDONTWRITEBYTECODE=1
exec "$IES_PYTHON" scripts/server.py review workflow-cv --config "$IES_REMOTE_CONFIG" --job-id "$1" --source-commit "$2"
