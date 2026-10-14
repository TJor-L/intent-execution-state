#!/usr/bin/env bash
# Source from a job submitted with --chdir pointing to the source checkout.
set -euo pipefail
if [[ -z "${IES_EXPECTED_COMMIT:-}" ]] || \
   [[ "$(git rev-parse HEAD)" != "$IES_EXPECTED_COMMIT" ]] || \
   [[ -n "$(git status --porcelain)" ]]; then
  echo 'Source revision changed or is uncommitted; resubmit from the reviewed checkout.' >&2
  exit 2
fi
# Use the submitted checkout rather than a stale installed copy of ies.
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
