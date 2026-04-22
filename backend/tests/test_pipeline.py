from __future__ import annotations

import io
import json
from typing import Any, Dict, List, Tuple

import pytest
from botocore.exceptions import ClientError

from backend.src import pipeline


class FakeBody:
    def __init__(self, text: str) -> None:
        self._text = text

    def read(self) -> bytes:
        return self._text.encode("utf-8")


class FakeS3Client:
    def __init__(self, existing_dataset: Dict[str, Any] | None = None) -> None:
        self.existing_dataset = existing_dataset
        self.puts: List[Tuple[str, str, bytes, str]] = []

    def get_object(self, Bucket: str, Key: str):
        if self.existing_dataset is None:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "not found"}},
                "GetObject",
            )
        payload = json.dumps(self.existing_dataset)
        return {"Body": FakeBody(payload)}

    def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str):
        self.puts.append((Bucket, Key, Body, ContentType))
        return {"ETag": "fake"}


def _topic_item_ids(dataset: Dict[str, Any]) -> List[int]:
    ids: List[int] = []
    for topic in dataset.get("topics", []):
        for subtopic in topic.get("subtopics", []):
            for item in subtopic.get("items", []):
                ids.append(item["id"])
    return sorted(ids)


def test_pipeline_writes_raw_and_dataset_without_existing(monkeypatch):
    monkeypatch.setattr(pipeline.config, "RAW_BUCKET", "raw-bucket")
    monkeypatch.setattr(pipeline.config, "CURATED_BUCKET", "curated-bucket")
    monkeypatch.setattr(pipeline.config, "RAW_KEY", "raw/objects.jsonl")
    monkeypatch.setattr(pipeline.config, "DATASET_KEY", "datasets/topic_tree.json")
    monkeypatch.setattr(pipeline.config, "APPEND_MODE", True)

    mock_records = [
        {
            "id": 1,
            "title": "A",
            "classification": "Paintings",
            "period": "Baroque",
            "primaryimageurl": "https://img/1",
            "imagepermissionlevel": 0,
        },
        {
            "id": 2,
            "title": "B",
            "classification": "Prints",
            "century": "19th century",
            "primaryimageurl": "https://img/2",
            "imagepermissionlevel": 0,
        },
    ]
    monkeypatch.setattr(pipeline, "iter_object_records", lambda: iter(mock_records))

    fake_s3 = FakeS3Client(existing_dataset=None)
    result = pipeline.run_ingestion_pipeline(s3_client=fake_s3)

    assert result.raw_records_count == 2
    assert result.normalized_records_count == 2
    assert result.raw_s3_uri == "s3://raw-bucket/raw/objects.jsonl"
    assert result.dataset_s3_uri == "s3://curated-bucket/datasets/topic_tree.json"
    assert len(fake_s3.puts) == 2

    raw_put = fake_s3.puts[0]
    assert raw_put[0] == "raw-bucket"
    assert raw_put[1] == "raw/objects.jsonl"
    assert raw_put[3] == "application/x-ndjson"
    assert raw_put[2].decode("utf-8").count("\n") == 2

    dataset_put = fake_s3.puts[1]
    dataset_json = json.loads(dataset_put[2].decode("utf-8"))
    assert _topic_item_ids(dataset_json) == [1, 2]


def test_pipeline_append_mode_merges_existing(monkeypatch):
    monkeypatch.setattr(pipeline.config, "RAW_BUCKET", "raw-bucket")
    monkeypatch.setattr(pipeline.config, "CURATED_BUCKET", "curated-bucket")
    monkeypatch.setattr(pipeline.config, "APPEND_MODE", True)

    existing = {
        "topics": [
            {
                "id": "classification:Paintings",
                "name": "Paintings",
                "count": 1,
                "subtopics": [
                    {
                        "id": "era:Baroque",
                        "name": "Baroque",
                        "eraSource": "period",
                        "count": 1,
                        "items": [{"id": 10, "title": "Old"}],
                    }
                ],
            }
        ],
        "lastUpdated": "2026-01-01T00:00:00Z",
        "source": {"endpoint": "/object", "filters": {"hasimage": 1}},
    }

    incoming_records = [
        {
            "id": 11,
            "title": "New",
            "classification": "Prints",
            "century": "19th century",
            "primaryimageurl": "https://img/11",
            "imagepermissionlevel": 0,
        }
    ]
    monkeypatch.setattr(pipeline, "iter_object_records", lambda: iter(incoming_records))

    fake_s3 = FakeS3Client(existing_dataset=existing)
    result = pipeline.run_ingestion_pipeline(s3_client=fake_s3)
    assert result.merged_records_count == 2

    dataset_put = fake_s3.puts[1]
    dataset_json = json.loads(dataset_put[2].decode("utf-8"))
    assert _topic_item_ids(dataset_json) == [10, 11]


def test_pipeline_requires_bucket_config(monkeypatch):
    monkeypatch.setattr(pipeline.config, "RAW_BUCKET", "")
    monkeypatch.setattr(pipeline.config, "CURATED_BUCKET", "curated-bucket")
    monkeypatch.setattr(pipeline, "iter_object_records", lambda: iter([]))

    fake_s3 = FakeS3Client(existing_dataset=None)
    with pytest.raises(ValueError):
        pipeline.run_ingestion_pipeline(s3_client=fake_s3)

