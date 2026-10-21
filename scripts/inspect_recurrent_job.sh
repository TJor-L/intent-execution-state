#!/usr/bin/env bash
# Read existing scheduler/operational records only. No submission or input replay.
set -euo pipefail
if [[ $# -ne 3 || ! "$1" =~ ^[0-9]{1,20}$ || ! "$2" =~ ^[a-f0-9]{40}$ ]]; then
  echo 'Usage: bash scripts/inspect_recurrent_job.sh JOB_ID SOURCE_COMMIT PRIVATE_OUTPUT_ROOT' >&2
  exit 2
fi
IES_INSPECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
IES_ORIGINAL_ROOT="$(cd "$IES_INSPECT_ROOT" && cd "$(git rev-parse --git-common-dir)/.." && pwd -P)"
cd "$IES_ORIGINAL_ROOT"
IES_INSPECT_UV="$(command -v uv || printf '%s' "$PWD/.tools/bin/uv")"
IES_INSPECT_PYTHON="$("$IES_INSPECT_UV" run --locked --no-sync python -c 'import sys; print(sys.executable)')"
export PYTHONPATH="$IES_INSPECT_ROOT/src"
export PYTHONDONTWRITEBYTECODE=1
if ! sacct -j "$1" --format=JobID,State,ExitCode,Elapsed,Timelimit,ReqMem,MaxRSS --parsable2; then
  echo 'Scheduler accounting unavailable; inspecting existing records only.'
fi
exec "$IES_INSPECT_PYTHON" "$IES_INSPECT_ROOT/scripts/inspect_recurrent_job.py" "$@"
