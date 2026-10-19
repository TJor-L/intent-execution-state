#!/usr/bin/env bash
# Optional private source path is entered only on UCSF, never copied into Git/chat.
set -euo pipefail
if [[ $# -gt 1 ]]; then
  echo 'Usage: bash scripts/probe_format.sh [AUTHORIZED_NEW_DATA_ROOT]' >&2
  exit 2
fi
IES_PROBE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
IES_ORIGINAL_ROOT="$(cd "$IES_PROBE_ROOT" && cd "$(git rev-parse --git-common-dir)/.." && pwd -P)"
cd "$IES_ORIGINAL_ROOT"
IES_REMOTE_CONFIG="$PWD/configs/remote.local.yaml"
IES_UV="$(command -v uv || printf '%s' "$PWD/.tools/bin/uv")"
IES_PYTHON="$("$IES_UV" run --locked --no-sync python -c 'import sys; print(sys.executable)')"
cd "$IES_PROBE_ROOT"
export IES_EXECUTION_CONTEXT=ucsf
export PYTHONPATH="$PWD/src"
export PYTHONDONTWRITEBYTECODE=1
IES_PROBE_OPTIONS=()
if [[ $# -eq 1 ]]; then
  IES_PROBE_OPTIONS=(--probe-root "$1")
fi
"$IES_PYTHON" scripts/server.py preflight --config "$IES_REMOTE_CONFIG"
"$IES_PYTHON" scripts/server.py plan format-probe --config "$IES_REMOTE_CONFIG" "${IES_PROBE_OPTIONS[@]}"
exec "$IES_PYTHON" scripts/server.py submit format-probe --config "$IES_REMOTE_CONFIG" "${IES_PROBE_OPTIONS[@]}" --wait
