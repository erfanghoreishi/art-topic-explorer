"""Step 5 pipeline: write raw and curated datasets to S3."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from . import config
from .grouping import build_paginated_views, build_topic_tree, merge_datasets
from .harvard_object_fetcher import iter_object_records
from .normalizer import normalize_object_record


JsonDict = Dict[str, Any]


@dataclass(frozen=True)
class PipelineResult:
    raw_records_count: int
    normalized_records_count: int
    merged_records_count: int
    start_page: int
    pages_requested: int
    raw_s3_uri: str
    dataset_s3_uri: str
    topics_index_s3_uri: str = ""
    topic_pages_count: int = 0


def _s3_client():
    return boto3.client("s3", region_name=config.AWS_REGION)


def _require_bucket(name: str, value: str) -> str:
    bucket = value.strip()
    if not bucket:
        raise ValueError(f"Missing required bucket config: {name}")
    return bucket


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _to_jsonl(records: List[JsonDict]) -> str:
    lines = [_json_dumps(record) for record in records]
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _read_existing_dataset(s3_client) -> Optional[JsonDict]:
    bucket = _require_bucket("CURATED_BUCKET", config.CURATED_BUCKET)
    key = config.DATASET_KEY
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        error_code = str(exc.response.get("Error", {}).get("Code", ""))
        if error_code in {"NoSuchKey", "404"}:
            return None
        raise

    body = response["Body"].read()
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    if not body:
        return None
    return json.loads(body)


def _read_ingestion_state(s3_client) -> JsonDict:
    bucket = _require_bucket("CURATED_BUCKET", config.CURATED_BUCKET)
    key = config.INGESTION_STATE_KEY
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        error_code = str(exc.response.get("Error", {}).get("Code", ""))
        if error_code in {"NoSuchKey", "404"}:
            return {}
        raise

    body = response["Body"].read()
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    if not body:
        return {}
    return json.loads(body)


def _write_ingestion_state(s3_client, state: JsonDict) -> None:
    bucket = _require_bucket("CURATED_BUCKET", config.CURATED_BUCKET)
    key = config.INGESTION_STATE_KEY
    payload = json.dumps(state, ensure_ascii=True, indent=2)
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=payload.encode("utf-8"),
        ContentType="application/json",
    )


def _write_raw_jsonl(s3_client, raw_records: List[JsonDict]) -> str:
    bucket = _require_bucket("RAW_BUCKET", config.RAW_BUCKET)
    key = config.RAW_KEY
    payload = _to_jsonl(raw_records)
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=payload.encode("utf-8"),
        ContentType="application/x-ndjson",
    )
    return f"s3://{bucket}/{key}"


def _write_dataset_json(s3_client, dataset: JsonDict) -> str:
    bucket = _require_bucket("CURATED_BUCKET", config.CURATED_BUCKET)
    key = config.DATASET_KEY
    payload = json.dumps(dataset, ensure_ascii=True, indent=2)
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=payload.encode("utf-8"),
        ContentType="application/json",
    )
    return f"s3://{bucket}/{key}"


def _topic_page_key(page_num: int) -> str:
    return f"{config.TOPICS_PAGE_PREFIX}{page_num}.json"


def _read_topics_index(s3_client) -> Optional[JsonDict]:
    bucket = _require_bucket("CURATED_BUCKET", config.CURATED_BUCKET)
    try:
        response = s3_client.get_object(Bucket=bucket, Key=config.TOPICS_INDEX_KEY)
    except ClientError as exc:
        error_code = str(exc.response.get("Error", {}).get("Code", ""))
        if error_code in {"NoSuchKey", "404"}:
            return None
        raise
    body = response["Body"].read()
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    if not body:
        return None
    return json.loads(body)


def _write_topic_page(s3_client, page_num: int, payload: JsonDict) -> str:
    bucket = _require_bucket("CURATED_BUCKET", config.CURATED_BUCKET)
    key = _topic_page_key(page_num)
    body = json.dumps(payload, ensure_ascii=True, indent=2)
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json",
    )
    return f"s3://{bucket}/{key}"


def _write_topics_index(s3_client, payload: JsonDict) -> str:
    bucket = _require_bucket("CURATED_BUCKET", config.CURATED_BUCKET)
    key = config.TOPICS_INDEX_KEY
    body = json.dumps(payload, ensure_ascii=True, indent=2)
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json",
    )
    return f"s3://{bucket}/{key}"


def _delete_stale_pages(s3_client, old_last_page: int, new_last_page: int) -> None:
    if old_last_page <= new_last_page:
        return
    bucket = _require_bucket("CURATED_BUCKET", config.CURATED_BUCKET)
    for page_num in range(new_last_page + 1, old_last_page + 1):
        try:
            s3_client.delete_object(Bucket=bucket, Key=_topic_page_key(page_num))
        except ClientError:
            # Best-effort cleanup; do not abort publish on a stale-delete failure.
            pass


def _publish_paginated_topics(s3_client, dataset: JsonDict) -> tuple[str, int]:
    """Write page files first, then the index. Cleans up stale page files when shrinking."""
    pages, index = build_paginated_views(
        dataset, config.TOPICS_PAGE_SIZE, config.TOPICS_MAX_PAGES
    )
    prior_index = _read_topics_index(s3_client)
    prior_last_page = int((prior_index or {}).get("lastPage", 0) or 0)

    for page_payload in pages:
        _write_topic_page(s3_client, page_payload["page"], page_payload)

    _delete_stale_pages(s3_client, prior_last_page, index["lastPage"])
    index_uri = _write_topics_index(s3_client, index)
    return index_uri, len(pages)


def run_ingestion_pipeline(s3_client=None) -> PipelineResult:
    """
    Run one ingestion cycle:
    1. fetch `/object` records
    2. write raw records as jsonl to S3
    3. normalize and build incoming topic tree
    4. merge with existing dataset in append mode
    5. write merged dataset to S3
    """
    client = s3_client or _s3_client()

    state = _read_ingestion_state(client)
    start_page = int(state.get("nextStartPage", config.INGESTION_START_PAGE) or config.INGESTION_START_PAGE)
    max_pages = max(config.HARVARD_MAX_PAGES, 1)

    raw_records: List[JsonDict] = []
    normalized_records: List[JsonDict] = []

    for record in iter_object_records(start_page=start_page, max_pages=max_pages):
        raw_records.append(record)
        normalized = normalize_object_record(record)
        if normalized is not None:
            normalized_records.append(normalized)

    incoming = build_topic_tree(normalized_records)
    existing = _read_existing_dataset(client)

    if config.APPEND_MODE and existing:
        final_dataset = merge_datasets(existing, incoming)
    else:
        final_dataset = incoming

    raw_uri = _write_raw_jsonl(client, raw_records)
    dataset_uri = _write_dataset_json(client, final_dataset)
    topics_index_uri, topic_pages_count = _publish_paginated_topics(client, final_dataset)
    _write_ingestion_state(
        client,
        {
            "nextStartPage": start_page + max_pages,
            "lastStartPage": start_page,
            "lastPagesRequested": max_pages,
            "lastRawRecordsCount": len(raw_records),
        },
    )

    merged_count = sum(
        len(subtopic.get("items", []))
        for topic in final_dataset.get("topics", [])
        for subtopic in topic.get("subtopics", [])
    )

    return PipelineResult(
        raw_records_count=len(raw_records),
        normalized_records_count=len(normalized_records),
        merged_records_count=merged_count,
        start_page=start_page,
        pages_requested=max_pages,
        raw_s3_uri=raw_uri,
        dataset_s3_uri=dataset_uri,
        topics_index_s3_uri=topics_index_uri,
        topic_pages_count=topic_pages_count,
    )
