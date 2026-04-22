"""Step 5 pipeline: write raw and curated datasets to S3."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from . import config
from .grouping import build_topic_tree, merge_datasets
from .harvard_object_fetcher import iter_object_records
from .normalizer import normalize_object_record


JsonDict = Dict[str, Any]


@dataclass(frozen=True)
class PipelineResult:
    raw_records_count: int
    normalized_records_count: int
    merged_records_count: int
    raw_s3_uri: str
    dataset_s3_uri: str


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

    raw_records: List[JsonDict] = []
    normalized_records: List[JsonDict] = []

    for record in iter_object_records():
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

    merged_count = sum(
        len(subtopic.get("items", []))
        for topic in final_dataset.get("topics", [])
        for subtopic in topic.get("subtopics", [])
    )

    return PipelineResult(
        raw_records_count=len(raw_records),
        normalized_records_count=len(normalized_records),
        merged_records_count=merged_count,
        raw_s3_uri=raw_uri,
        dataset_s3_uri=dataset_uri,
    )

