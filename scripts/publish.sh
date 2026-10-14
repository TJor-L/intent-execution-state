#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -n "$(git status --porcelain)" ]]; then
  echo 'Commit verified source changes before publishing.' >&2
  exit 2
fi
if ! git remote get-url origin >/dev/null 2>&1; then
  echo 'No origin configured. Add the repository URL supplied by the user first.' >&2
  exit 2
fi
branch="$(git symbolic-ref --short HEAD)"
make check
make handoff
git push --set-upstream origin "$branch"
