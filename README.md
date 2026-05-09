# Harvard Art Museums Topic Explorer

Image-first topic browser over the Harvard Art Museums collection, built on a scheduled ingestion pipeline that publishes a static dataset to S3.

---

## Overview

**Problem**
The Harvard Art Museums API is rich but raw — browsing by topic, era, or classification requires non-trivial querying that isn't practical to do client-side on every page load.

**Solution**
A scheduled Lambda fetches and normalises objects from the `/object` endpoint, groups them by `Classification → Era → Artwork`, and writes a single snapshot JSON to S3. The frontend reads that file directly — no per-request API calls.

**Key Features**
- Paged ingestion with append/dedupe against the existing dataset
- Era derivation: `period` → `century` → `"Unknown Era"`
- Admin API (shared-secret) for manual refresh and schedule changes
- CloudWatch alarms for Lambda errors and dataset freshness
- Paginated topic outputs (`datasets/topics_index.json` + `datasets/topics/page_<n>.json`) so the frontend only loads the visible page

---

## Dataset contract

The ingestion pipeline publishes three artifacts under `s3://CURATED_BUCKET/datasets/`:

1. **`topic_tree.json`** *(legacy/full)* — single monolithic tree (`Classification → Era → Items`). Still written for backward compatibility and used by the frontend for drill-down (classification/era/artwork detail pages).
2. **`topics_index.json`** *(manifest)* — small file the frontend fetches first.
   ```json
   {
     "lastUpdated": "2026-05-09T12:34:56+00:00",
     "totalTopics": 60,
     "exposedTopics": 60,
     "pageSize": 6,
     "lastPage": 10,
     "maxPages": 10,
     "version": "2026-05-09T12:34:56+00:00",
     "pages": ["page_1.json", "page_2.json", ...]
   }
   ```
3. **`topics/page_<n>.json`** *(per-page slice)* — `{ page, pageSize, totalTopics, lastPage, topics }`. Topics are sorted by count and chunked in `TOPICS_PAGE_SIZE` slices, capped at `TOPICS_PAGE_SIZE * TOPICS_MAX_PAGES`.

**Publish ordering invariant.** Each ingestion run writes all `page_<n>.json` files first, deletes any stale page files left over from a smaller previous run, and then writes `topics_index.json` last. This guarantees clients never see an index pointing at a page that hasn't been written yet.

**Bucket policy.** `datasets/*` (recursive) must be public-read for the frontend to fetch index and page files directly. The existing `s3:GetObject` allow on `datasets/*` covers the new keys without changes.

---

## Tech Stack

- Python 3
- AWS Lambda, EventBridge, S3, SNS, CloudWatch
- Plain JavaScript frontend (no framework)
- pytest
- GitHub Actions (CI + deploy)

---

## Architecture

```
EventBridge rule (ham-topic-explorer-refresh, eu-west-2)
    └─> ham-topic-explorer-ingestion (Lambda)
            ├─> Harvard Art Museums API (/object, paged)
            ├─> s3://ham-topic-explorer-raw-*/ raw/objects.jsonl
            └─> s3://ham-topic-explorer-curated-*/ datasets/topic_tree.json
                    └─> public read (s3:GetObject on datasets/*)

API Gateway (POST /admin)  https://q8fhj5i6oi.execute-api.eu-west-2.amazonaws.com/main
    └─> ham-topic-explorer-admin (Lambda)
            ├─> auth-check      (validates x-admin-token)
            ├─> refresh-now     (invokes ingestion Lambda directly, cooldown-gated)
            └─> set-schedule    (preset-only; calls events:PutRule on EventBridge rule)
                    └─> reads/writes cooldown state to curated S3 admin/

museum.ghoreishi.dev  (Cloudflare A → EC2, eu-west-2)
    └─> /home/ubuntu/museum.ghoreishi.dev  (frontend static files)
            └─> fetches datasets/topic_tree.json from curated S3 bucket
```

S3 buckets (eu-west-2):

| Bucket | Public | Purpose |
|---|---|---|
| `ham-topic-explorer-raw-*` | No | Raw JSONL from each ingestion run |
| `ham-topic-explorer-curated-*` | `datasets/*` only | Merged topic tree + admin state |
| `ham-topic-explorer-frontend-*` | Yes (static hosting) | Frontend fallback / S3 static site |

SQS and Step Functions are provisioned as placeholders for a future phase.

---

## Installation

### 1. Clone repository
```bash
git clone https://github.com/yourusername/art-knowledge-explorer.git
cd art-knowledge-explorer
```

### 2. Configure environment
```bash
cp .env.example .env
```

Minimum required for local ingestion runs:
- `HARVARD_ART_API_KEY`
- `RAW_BUCKET`
- `CURATED_BUCKET`

### 3. Install dependencies
```bash
pip install -r backend/requirements.txt
```

---

## Usage

### Run ingestion locally
```bash
./.venv/bin/python -c "from backend.src.pipeline import run_ingestion_pipeline; print(run_ingestion_pipeline())"
```

Writes:
- `s3://$RAW_BUCKET/$RAW_KEY` — raw records as JSONL
- `s3://$CURATED_BUCKET/$DATASET_KEY` — merged topic tree as JSON

### Generate a local demo dataset (no S3 needed)
```bash
./.venv/bin/python -m backend.src.local_demo --max-pages 5
```

Writes `frontend/dataset.json`. Serve with:
```bash
python3 -m http.server 8080
# open http://localhost:8080/frontend/
```

### Admin API

```bash
# Manual refresh
curl -X POST https://<admin-api-url> \
  -H "x-admin-token: <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"action":"refresh-now"}'

# Change schedule
curl -X POST https://<admin-api-url> \
  -H "x-admin-token: <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"action":"set-schedule","preset":"daily"}'
```

Allowed schedule presets: `hourly`, `every_6_hours`, `daily`.

---

## Running Tests

```bash
# Offline tests only
pytest -q backend/tests -k "not real_api"

# Real API smoke test (requires key)
export HARVARD_ART_API_KEY=...
export RUN_REAL_API_TESTS=true
pytest -q backend/tests/test_real_api_integration.py
```

---

## Project Structure

```
backend/
├── src/
│   ├── config.py
│   ├── harvard_object_contract.py
│   ├── pipeline.py
│   ├── lambda_handler.py
│   ├── admin_handler.py
│   ├── cloudwatch_setup.py
│   └── local_demo.py
├── tests/
└── requirements.txt
frontend/
├── index.html
├── styles.css
├── config.js
└── app.js
scripts/
└── package_lambda.sh
.github/
└── workflows/
    ├── ci.yml
    └── deploy-main.yml
```

---

## CI/CD

Two GitHub Actions workflows:

- **`ci.yml`** — runs tests and syntax checks on PRs and `main` pushes
- **`deploy-main.yml`** — runs tests, builds the Lambda bundle, updates Lambda env vars and code, renders `frontend/config.js`, and rsyncs frontend files to an EC2 host

See `.github/actions-vars.example` and `.github/actions-secrets.example` for the full list of required repository variables and secrets.

### Syncing GitHub Actions variables

`.github/actions-vars.example` is the **source of truth** for GitHub Actions repository variables. The deploy workflow reads `${{ vars.* }}` at the start of each run, so any edits to this file must be pushed to GitHub vars **before** triggering a deploy — otherwise the new values won't take effect until the *next* run.

```bash
gh auth login                                # one-time, needs `repo` scope
./scripts/sync-github-vars.sh                # apply each KEY=VALUE in the file
git push                                     # then trigger the deploy
```

The script is a thin loop over the file calling `gh variable set` per line — repo is auto-detected from your git remote. The deploy workflow prints a `::warning::` reminder at the start of each run as a safety net. Only **variables** are managed here; secrets (`HARVARD_ART_API_KEY`, `ADMIN_TOKEN`, `EC2_SSH_PRIVATE_KEY`) are set separately via `gh secret set`.