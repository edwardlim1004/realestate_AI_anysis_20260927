#!/usr/bin/env bash
# Retry non-fast-forward races; never overwrite a conflicting generated file.
set -euo pipefail
for attempt in 1 2 3 4; do
  git fetch origin main
  if ! git rebase origin/main; then
    git rebase --abort
    echo 'Concurrent changes conflict; preserve remote data and fail for review.' >&2
    exit 1
  fi
  if git push origin HEAD:main; then exit 0; fi
done
echo 'Concurrent branch updates exhausted push retries.' >&2
exit 1
