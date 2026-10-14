#!/usr/bin/env bash
#SBATCH --job-name=ies-synthetic-evaluation
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
umask 077
if [[ $# -ne 4 ]]; then
  echo 'Arguments: python_executable synthetic_cohort synthetic_model new_output_directory' >&2
  exit 2
fi
source slurm/verify_source.sh
exec "$1" -m ies.cli evaluate --cohort "$2" --model "$3" --output-dir "$4"
