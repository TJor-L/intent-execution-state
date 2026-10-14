#!/usr/bin/env bash
#SBATCH --job-name=ies-synthetic
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
umask 077
if [[ $# -ne 3 ]]; then
  echo 'Arguments: python_executable synthetic_config new_run_directory' >&2
  exit 2
fi
source slurm/verify_source.sh
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-2}"
exec "$1" -m ies.cli run --config "$2" --run-dir "$3"
