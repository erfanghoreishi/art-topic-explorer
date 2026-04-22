# Harvard Art Museums Topic Explorer (1-Day MVP)

Image-first prototype using **only** Harvard Art Museums `GET /object`, with a static dataset published to S3 for frontend browsing:

`Classification -> Era -> Artwork`

## Locked decisions

- Data source: only `/object`
- Era rule: `period` -> `century` -> `"Unknown Era"`
- UI data mode: single snapshot JSON in S3 (no per-object live fetch)
- Refresh policy: append new ingestion results into existing S3 dataset with dedupe by artwork id
- Day-one real services: EventBridge, Lambda, S3, CloudWatch, SNS
- SQS and Step Functions: provisioned as placeholders for phase 1.5

## Backend layout

- `backend/src/config.py` runtime env config
- `backend/src/harvard_object_contract.py` locked `/object` request contract

## Environment

Copy `.env.example` to `.env` and fill values:

```bash
cp .env.example .env
```

Required minimum for local ingestion tests:

- `HARVARD_ART_API_KEY`
- `RAW_BUCKET`
- `CURATED_BUCKET`

## Step-by-step delivery mode

Implementation proceeds in checkpoints:

1. Scaffold + env + field contract
2. `/object` paged fetch generator
3. Normalizer + era derivation
4. Grouping builder
5. S3 writes (`raw.jsonl`, `dataset.json`)
6. Lambda + EventBridge + SNS wiring
7. CloudWatch alarms
8. Frontend pages
9. End-to-end polish

## Append policy (locked)

- Each scheduled run reads current `dataset.json` from S3 (if present), merges new records, then writes back.
- Merge key: artwork `id` (fallback `objectid`), latest version wins on collisions.
- `MAX_ITEMS_PER_ERA` applies to the **post-merge total per era** in the final dataset.

## Tests

Install dependencies:

```bash
pip install -r backend/requirements.txt
```

Run local/offline tests:

```bash
pytest -q backend/tests -k "not real_api"
```

Run real Harvard API smoke test (optional):

```bash
export HARVARD_ART_API_KEY=...
export RUN_REAL_API_TESTS=true
pytest -q backend/tests/test_real_api_integration.py
```

## Step 5: S3 pipeline run (local)

Run one ingestion cycle (fetch -> normalize -> merge -> S3 write):

```bash
./.venv/bin/python -c "from backend.src.pipeline import run_ingestion_pipeline; print(run_ingestion_pipeline())"
```

This writes:
- raw records to `s3://$RAW_BUCKET/$RAW_KEY` as JSONL
- merged dataset to `s3://$CURATED_BUCKET/$DATASET_KEY` as JSON

## Step 6: Lambda handler

Lambda entrypoint:

- `backend.src.lambda_handler.handler`

Local invoke simulation:

```bash
./.venv/bin/python -c "from backend.src.lambda_handler import handler; print(handler({'source':'aws.events'}, None))"
```

## Step 7: CloudWatch alarms

Configured alarms:
- `LAMBDA_FUNCTION_NAME-errors` on `AWS/Lambda Errors >= 1` (5-minute window)
- `LAMBDA_FUNCTION_NAME-dataset-freshness-hours` on custom metric `ArtKnowledgeExplorer/DatasetAgeHours`

Apply alarms:

```bash
./.venv/bin/python -c "from backend.src.cloudwatch_setup import apply_alarms; print(apply_alarms())"
```

Notes:
- If `SNS_TOPIC_ARN` is set, alarms send `ALARM/OK` actions to that topic.
- Freshness alarm expects `DatasetAgeHours` metric publishing (can be added in next step).

## Step 8: Frontend (plain JavaScript)

Files:
- `frontend/index.html`
- `frontend/styles.css`
- `frontend/config.js`
- `frontend/app.js`

Set dataset URL in `frontend/config.js`:

```js
window.APP_CONFIG = {
  datasetUrl: "https://<your-bucket-or-cdn>/datasets/topic_tree.json",
};
```

Local static serve example:

```bash
python3 -m http.server 8080
```

Then open:
- `http://localhost:8080/frontend/`

## Step 9: End-to-end dry run + demo polish

Generate local demo dataset (no S3 needed):

```bash
./.venv/bin/python -m backend.src.local_demo --max-pages 5
```

This writes:
- `frontend/dataset.json` (or `LOCAL_DEMO_DATASET_PATH`)

Demo sequence:
1. Start static server: `python3 -m http.server 8080`
2. Open `http://localhost:8080/frontend/`
3. Walk through:
   - Classifications
   - One classification's eras
   - Artwork grid
   - Detail modal
4. Use Refresh button once to show data reload
