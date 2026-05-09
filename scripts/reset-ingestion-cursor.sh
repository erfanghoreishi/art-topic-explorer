#!/usr/bin/env bash
# Delete the ingestion cursor in S3 so the next ingestion run starts from
# INGESTION_START_PAGE (page 1 by default) with the current HARVARD_PAGE_SIZE.
#
# Run this whenever you change HARVARD_PAGE_SIZE or HARVARD_MAX_PAGES, because
# the saved nextStartPage is in Harvard's pagination units and shifts meaning
# when the page size changes.
#
# Usage: ./scripts/reset-ingestion-cursor.sh
# Reads CURATED_BUCKET and INGESTION_STATE_KEY from .github/actions-vars.example.
# run this manualy on cloudshell: aws s3 rm s3://ham-topic-explorer-curated-877485452489-eu-west-2-an/admin/ingestion_state.json

set -euo pipefail

VARS_FILE=".github/actions-vars.example"

if [[ ! -f "$VARS_FILE" ]]; then
  echo "ERROR: $VARS_FILE not found" >&2
  exit 1
fi

# shellcheck disable=SC1090
get_var() { grep -E "^${1}=" "$VARS_FILE" | head -n1 | cut -d'=' -f2-; }

BUCKET="$(get_var CURATED_BUCKET)"
KEY="$(get_var INGESTION_STATE_KEY)"
REGION="$(get_var AWS_REGION)"

if [[ -z "$BUCKET" || -z "$KEY" ]]; then
  echo "ERROR: CURATED_BUCKET or INGESTION_STATE_KEY missing in $VARS_FILE" >&2
  exit 1
fi

echo "Deleting s3://$BUCKET/$KEY (region: ${REGION:-default})"
aws s3 rm "s3://$BUCKET/$KEY" --region "${REGION:-eu-west-2}"
echo "Done. Next ingestion run will start from page 1."
