#!/usr/bin/env bash
#SBATCH --job-name=ies-clinical-features
#SBATCH --nodes=1
#SBATCH --ntasks=1
set -euo pipefail
umask 077
if [[ $# -ne 5 || "${IES_EXECUTION_CONTEXT:-}" != ucsf ]]; then
  echo 'Use the configured UCSF clinical-features submission entry point.' >&2
  exit 2
fi
source slurm/verify_source.sh
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"
exec "$1" -m ies.cli clinical-features run --mapping "$2" --protocol "$3" --cohort-dir "$4" --output-dir "$5"
