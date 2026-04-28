"""Lambda entrypoint for scheduled ingestion runs (Step 6)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3

from . import config
from .pipeline import PipelineResult, run_ingestion_pipeline


JsonDict = Dict[str, Any]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sns_client():
    return boto3.client("sns", region_name=config.AWS_REGION)


def _publish_status(message: JsonDict, sns_client=None) -> None:
    topic_arn = (config.SNS_TOPIC_ARN or "").strip()
    if not topic_arn:
        return

    client = sns_client or _sns_client()
    client.publish(
        TopicArn=topic_arn,
        Subject=message.get("subject", "Harvard Topic Explorer Ingestion"),
        Message=json.dumps(message, ensure_ascii=True),
    )


def _success_payload(result: PipelineResult, trigger_event: Optional[JsonDict]) -> JsonDict:
    return {
        "subject": "Harvard Topic Explorer Ingestion Succeeded",
        "status": "success",
        "timestamp": _now_iso(),
        "triggerSource": (trigger_event or {}).get("source", "unknown"),
        "rawRecordsCount": result.raw_records_count,
        "normalizedRecordsCount": result.normalized_records_count,
        "mergedRecordsCount": result.merged_records_count,
        "startPage": result.start_page,
        "pagesRequested": result.pages_requested,
        "rawS3Uri": result.raw_s3_uri,
        "datasetS3Uri": result.dataset_s3_uri,
    }


def _failure_payload(error: Exception, trigger_event: Optional[JsonDict]) -> JsonDict:
    return {
        "subject": "Harvard Topic Explorer Ingestion Failed",
        "status": "error",
        "timestamp": _now_iso(),
        "triggerSource": (trigger_event or {}).get("source", "unknown"),
        "errorType": type(error).__name__,
        "errorMessage": str(error),
    }


def handler(event: Optional[JsonDict], context: Any) -> JsonDict:
    """
    AWS Lambda handler for scheduled ingestion.

    Intended trigger: EventBridge schedule.
    """
    try:
        result = run_ingestion_pipeline()
        payload = _success_payload(result, event)
        _publish_status(payload)
        return payload
    except Exception as exc:
        payload = _failure_payload(exc, event)
        _publish_status(payload)
        raise
