#!/usr/bin/env bash
# Sync GitHub Actions repository variables from a local env file.
# Reads .github/actions-vars.example by default and runs `gh variable set` per line.
#
# Usage:
#   ./scripts/sync-github-vars.sh                 # apply default file
#   ./scripts/sync-github-vars.sh path/to/file    # apply a different file
#
# Requires: gh CLI, authenticated (`gh auth login`) with repo scope.
# Repo is auto-detected from the current git remote.

set -euo pipefail

FILE="${1:-.github/actions-vars.example}"

if [[ ! -f "$FILE" ]]; then
  echo "ERROR: file not found: $FILE" >&2
  exit 1
fi

while IFS='=' read -r key value || [[ -n "$key" ]]; do
  # Skip blank lines and comments.
  [[ -z "${key// /}" ]] && continue
  [[ "${key:0:1}" == "#" ]] && continue

  echo "  setting $key"
  gh variable set "$key" --body "$value"

  # Track whether ingestion-batching vars changed.
  if [[ "$key" == "HARVARD_PAGE_SIZE" || "$key" == "HARVARD_MAX_PAGES" ]]; then
    BATCH_CHANGED=1
  fi
done < "$FILE"

echo "Done."

if [[ "${BATCH_CHANGED:-0}" -eq 1 ]]; then
  cat <<'WARN'

⚠️  HARVARD_PAGE_SIZE or HARVARD_MAX_PAGES was synced.
    The S3 cursor (admin/ingestion_state.json) is in Harvard pagination units —
    if you changed page size, "page N" now points at a different chunk of records.
    Reset the cursor before the next ingestion run:

        ./scripts/reset-ingestion-cursor.sh

WARN
fi
