#!/usr/bin/env bash
#SBATCH --job-name=ies-workflow-diagnostics
#SBATCH --nodes=1
#SBATCH --ntasks=1
set -euo pipefail
umask 077
if [[ $# -ne 6 || "${IES_EXECUTION_CONTEXT:-}" != ucsf ]]; then
  echo 'Use the configured UCSF workflow-diagnostics submission entry point.' >&2
  exit 2
fi
source slurm/verify_source.sh
exec "$1" -m ies.cli workflow-diagnostics run --cohort-dir "$2" --history-dir "$3" --config "$4" --workflow-dir "$5" --output-dir "$6"
