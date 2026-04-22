from __future__ import annotations

import json

import pytest

from backend.src import lambda_handler as lh
from backend.src.pipeline import PipelineResult


class FakeSns:
    def __init__(self) -> None:
        self.published = []

    def publish(self, TopicArn: str, Subject: str, Message: str):
        self.published.append(
            {"TopicArn": TopicArn, "Subject": Subject, "Message": json.loads(Message)}
        )
        return {"MessageId": "m-1"}


def test_handler_success_publishes_sns_when_topic_configured(monkeypatch):
    fake_sns = FakeSns()
    monkeypatch.setattr(lh.config, "SNS_TOPIC_ARN", "arn:aws:sns:eu-west-2:123:test-topic")
    monkeypatch.setattr(
        lh,
        "run_ingestion_pipeline",
        lambda: PipelineResult(
            raw_records_count=8,
            normalized_records_count=6,
            merged_records_count=10,
            raw_s3_uri="s3://raw/raw.jsonl",
            dataset_s3_uri="s3://curated/dataset.json",
        ),
    )
    monkeypatch.setattr(lh, "_sns_client", lambda: fake_sns)

    out = lh.handler({"source": "aws.events"}, context=None)
    assert out["status"] == "success"
    assert out["rawRecordsCount"] == 8
    assert len(fake_sns.published) == 1
    assert fake_sns.published[0]["Message"]["status"] == "success"


def test_handler_success_skips_sns_when_no_topic(monkeypatch):
    monkeypatch.setattr(lh.config, "SNS_TOPIC_ARN", "")
    monkeypatch.setattr(
        lh,
        "run_ingestion_pipeline",
        lambda: PipelineResult(
            raw_records_count=1,
            normalized_records_count=1,
            merged_records_count=1,
            raw_s3_uri="s3://raw/raw.jsonl",
            dataset_s3_uri="s3://curated/dataset.json",
        ),
    )
    out = lh.handler({"source": "aws.events"}, context=None)
    assert out["status"] == "success"
    assert out["datasetS3Uri"] == "s3://curated/dataset.json"


def test_handler_failure_publishes_and_raises(monkeypatch):
    fake_sns = FakeSns()
    monkeypatch.setattr(lh.config, "SNS_TOPIC_ARN", "arn:aws:sns:eu-west-2:123:test-topic")

    def _boom():
        raise RuntimeError("pipeline failed")

    monkeypatch.setattr(lh, "run_ingestion_pipeline", _boom)
    monkeypatch.setattr(lh, "_sns_client", lambda: fake_sns)

    with pytest.raises(RuntimeError):
        lh.handler({"source": "aws.events"}, context=None)

    assert len(fake_sns.published) == 1
    assert fake_sns.published[0]["Message"]["status"] == "error"
    assert "pipeline failed" in fake_sns.published[0]["Message"]["errorMessage"]

