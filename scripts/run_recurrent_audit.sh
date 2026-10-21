#!/usr/bin/env bash
# T001 is a declared full-source scan. Default is plan only; --submit runs it.
set -euo pipefail
umask 077
IES_TASK_ACTION=plan
if [[ "${1:-}" == "--submit" || "${1:-}" == "--check-storage" ]]; then
  IES_TASK_ACTION="${1#--}"
  shift
fi
IES_TASK_OUTPUT=()
if [[ "${1:-}" == "--output-root" && $# -ge 2 ]]; then
  IES_TASK_OUTPUT=(--output-root "$2")
  shift 2
fi
if [[ $# -gt 1 ]]; then
  echo 'Usage: bash scripts/run_recurrent_audit.sh [--submit|--check-storage] [--output-root PRIVATE_DIR] [EXISTING_ELIGIBILITY_MAPPING]' >&2
  exit 2
fi
IES_TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
IES_ORIGINAL_ROOT="$(cd "$IES_TASK_ROOT" && cd "$(git rev-parse --git-common-dir)/.." && pwd -P)"
cd "$IES_ORIGINAL_ROOT"
IES_TASK_CONFIG="$PWD/configs/remote.local.yaml"
IES_TASK_UV="$(command -v uv || printf '%s' "$PWD/.tools/bin/uv")"
IES_TASK_PYTHON="$("$IES_TASK_UV" run --locked --no-sync python -c 'import sys; print(sys.executable)')"
IES_TASK_MAPPING=()
if [[ $# -eq 1 ]]; then
  IES_TASK_MAPPING=(--mapping "$1")
fi
cd "$IES_TASK_ROOT"
export IES_EXECUTION_CONTEXT=ucsf
export PYTHONPATH="$PWD/src"
export PYTHONDONTWRITEBYTECODE=1
"$IES_TASK_PYTHON" scripts/server.py preflight --config "$IES_TASK_CONFIG"
if [[ "$IES_TASK_ACTION" == check-storage ]]; then
  exec "$IES_TASK_PYTHON" scripts/recurrent_audit.py check-storage --config "$IES_TASK_CONFIG" "${IES_TASK_MAPPING[@]}" "${IES_TASK_OUTPUT[@]}"
fi
"$IES_TASK_PYTHON" scripts/recurrent_audit.py plan --config "$IES_TASK_CONFIG" "${IES_TASK_MAPPING[@]}" "${IES_TASK_OUTPUT[@]}"
if [[ "$IES_TASK_ACTION" == submit ]]; then
  exec "$IES_TASK_PYTHON" scripts/recurrent_audit.py submit --config "$IES_TASK_CONFIG" "${IES_TASK_MAPPING[@]}" "${IES_TASK_OUTPUT[@]}"
fi
