#!/usr/bin/env bash
#SBATCH --job-name=ies-schema-audit
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
umask 077
if [[ $# -ne 5 || "${IES_EXECUTION_CONTEXT:-}" != ucsf ]]; then
  echo 'Use the configured UCSF server.py submission entry point.' >&2
  exit 2
fi
source slurm/verify_source.sh
exec "$1" -m ies.cli audit --data-root "$2" --output "$3" --max-files "$4" --max-directories "$5"
