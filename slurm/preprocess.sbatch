#!/usr/bin/env bash
#SBATCH --job-name=ies-synthetic-cohort
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
umask 077
if [[ $# -ne 4 ]]; then
  echo 'Arguments: python_executable synthetic_events output_cohort synthetic_config' >&2
  exit 2
fi
source slurm/verify_source.sh
exec "$1" -m ies.cli build-cohort --events "$2" --output "$3" --config "$4"
