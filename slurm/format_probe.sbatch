#!/usr/bin/env bash
#SBATCH --job-name=ies-format-probe
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:02:30
set -euo pipefail
umask 077
if [[ $# -ne 3 || "${IES_EXECUTION_CONTEXT:-}" != ucsf ]]; then
  echo 'Use the configured format-probe server entry point.' >&2
  exit 2
fi
source slurm/verify_source.sh
exec "$1" -m ies.format_probe_runner "$2" "$3"
