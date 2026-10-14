#!/usr/bin/env bash
#SBATCH --job-name=ies-feasibility
#SBATCH --nodes=1
#SBATCH --ntasks=1
# Resource ceilings are supplied by server.py from the validated mapping limits.
set -euo pipefail
umask 077
if [[ ( $# -ne 3 && $# -ne 4 ) || "${IES_EXECUTION_CONTEXT:-}" != ucsf ]]; then
  echo 'Use the configured UCSF bounded-feasibility submission entry point.' >&2
  exit 2
fi
source slurm/verify_source.sh
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"
export NUMEXPR_NUM_THREADS="$OMP_NUM_THREADS"
if [[ $# -eq 4 ]]; then
  exec "$1" -m ies.cli feasibility run --mapping "$2" --access-manifest "$3" --output-dir "$4"
fi
exec "$1" -m ies.cli feasibility run --mapping "$2" --output-dir "$3"
