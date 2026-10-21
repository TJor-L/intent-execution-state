#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 4 ]]; then
  echo 'Recurrent audit requires Python, existing mapping, cohort, and private output.' >&2
  exit 2
fi
export PYTHONPATH="$PWD/src"
export PYTHONDONTWRITEBYTECODE=1
exec "$1" -m ies.recurrent_task_runner "$2" "$3" "$4"
