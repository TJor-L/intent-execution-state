#!/usr/bin/env bash
# Run fixed R001 nested development benchmark; keep original held-out partitions sealed.
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo 'Usage: bash scripts/run_selection.sh ORIGINAL_JOB_ID ORIGINAL_JOB_COMMIT' >&2
  exit 2
fi
IES_SELECTION_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
IES_ORIGINAL_ROOT="$(cd "$IES_SELECTION_ROOT" && cd "$(git rev-parse --git-common-dir)/.." && pwd -P)"
cd "$IES_ORIGINAL_ROOT"
IES_REMOTE_CONFIG="$PWD/configs/remote.local.yaml"
IES_UV="$(command -v uv || printf '%s' "$PWD/.tools/bin/uv")"
IES_PYTHON="$("$IES_UV" run --locked --no-sync python -c 'import sys; print(sys.executable)')"
cd "$IES_SELECTION_ROOT"
export IES_EXECUTION_CONTEXT=ucsf
export PYTHONPATH="$PWD/src"
export PYTHONDONTWRITEBYTECODE=1
"$IES_PYTHON" scripts/server.py preflight --config "$IES_REMOTE_CONFIG"
"$IES_PYTHON" scripts/server.py plan workflow-selection --config "$IES_REMOTE_CONFIG" --auto-artifacts --job-id "$1" --source-commit "$2"
exec "$IES_PYTHON" scripts/server.py submit workflow-selection --config "$IES_REMOTE_CONFIG" --auto-artifacts --job-id "$1" --source-commit "$2" --wait
