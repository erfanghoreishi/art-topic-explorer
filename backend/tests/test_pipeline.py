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
    def __init__(
        self,
        existing_dataset: Dict[str, Any] | None = None,
        existing_topics_index: Dict[str, Any] | None = None,
    ) -> None:
        self.existing_dataset = existing_dataset
        self.existing_topics_index = existing_topics_index
        self.ingestion_state: Dict[str, Any] | None = None
        self.puts: List[Tuple[str, str, bytes, str]] = []
        self.deletes: List[Tuple[str, str]] = []

    def get_object(self, Bucket: str, Key: str):
        if Key.endswith("ingestion_state.json"):
            if self.ingestion_state is None:
                raise ClientError(
                    {"Error": {"Code": "NoSuchKey", "Message": "not found"}},
                    "GetObject",
                )
            return {"Body": FakeBody(json.dumps(self.ingestion_state))}
        if Key.endswith("topics_index.json"):
            if self.existing_topics_index is None:
                raise ClientError(
                    {"Error": {"Code": "NoSuchKey", "Message": "not found"}},
                    "GetObject",
                )
            return {"Body": FakeBody(json.dumps(self.existing_topics_index))}
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

    def delete_object(self, Bucket: str, Key: str):
        self.deletes.append((Bucket, Key))
        return {}


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
    monkeypatch.setattr(
        pipeline,
        "iter_object_records",
        lambda start_page=1, max_pages=None: iter(mock_records),
    )

    fake_s3 = FakeS3Client(existing_dataset=None)
    result = pipeline.run_ingestion_pipeline(s3_client=fake_s3)

    assert result.raw_records_count == 2
    assert result.normalized_records_count == 2
    assert result.raw_s3_uri == "s3://raw-bucket/raw/objects.jsonl"
    assert result.dataset_s3_uri == "s3://curated-bucket/datasets/topic_tree.json"
    assert result.topic_pages_count == 1
    assert result.topics_index_s3_uri.endswith("/datasets/topics_index.json")

    keys = [p[1] for p in fake_s3.puts]
    raw_put = next(p for p in fake_s3.puts if p[1] == "raw/objects.jsonl")
    assert raw_put[0] == "raw-bucket"
    assert raw_put[3] == "application/x-ndjson"
    assert raw_put[2].decode("utf-8").count("\n") == 2

    dataset_put = next(p for p in fake_s3.puts if p[1] == "datasets/topic_tree.json")
    dataset_json = json.loads(dataset_put[2].decode("utf-8"))
    assert _topic_item_ids(dataset_json) == [1, 2]
    assert any(k.endswith("ingestion_state.json") for k in keys)


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
    monkeypatch.setattr(
        pipeline,
        "iter_object_records",
        lambda start_page=1, max_pages=None: iter(incoming_records),
    )

    fake_s3 = FakeS3Client(existing_dataset=existing)
    result = pipeline.run_ingestion_pipeline(s3_client=fake_s3)
    assert result.merged_records_count == 2

    dataset_put = next(p for p in fake_s3.puts if p[1] == "datasets/topic_tree.json")
    dataset_json = json.loads(dataset_put[2].decode("utf-8"))
    assert _topic_item_ids(dataset_json) == [10, 11]


def test_pipeline_publishes_pages_before_index(monkeypatch):
    monkeypatch.setattr(pipeline.config, "RAW_BUCKET", "raw-bucket")
    monkeypatch.setattr(pipeline.config, "CURATED_BUCKET", "curated-bucket")
    monkeypatch.setattr(pipeline.config, "DATASET_KEY", "datasets/topic_tree.json")
    monkeypatch.setattr(pipeline.config, "TOPICS_INDEX_KEY", "datasets/topics_index.json")
    monkeypatch.setattr(pipeline.config, "TOPICS_PAGE_PREFIX", "datasets/topics/page_")
    monkeypatch.setattr(pipeline.config, "TOPICS_PAGE_SIZE", 1)
    monkeypatch.setattr(pipeline.config, "TOPICS_MAX_PAGES", 5)

    mock_records = [
        {
            "id": i,
            "title": f"T{i}",
            "classification": f"Class{i}",
            "century": "19th century",
            "primaryimageurl": f"https://img/{i}",
            "imagepermissionlevel": 0,
        }
        for i in range(1, 4)
    ]
    monkeypatch.setattr(
        pipeline,
        "iter_object_records",
        lambda start_page=1, max_pages=None: iter(mock_records),
    )

    fake_s3 = FakeS3Client(existing_dataset=None)
    result = pipeline.run_ingestion_pipeline(s3_client=fake_s3)

    assert result.topic_pages_count == 3
    keys = [p[1] for p in fake_s3.puts]
    page_keys = [k for k in keys if k.startswith("datasets/topics/page_")]
    assert page_keys == [
        "datasets/topics/page_1.json",
        "datasets/topics/page_2.json",
        "datasets/topics/page_3.json",
    ]
    last_page_idx = max(keys.index(k) for k in page_keys)
    index_idx = keys.index("datasets/topics_index.json")
    assert index_idx > last_page_idx, "topics_index.json must be written after all page files"

    index_put = next(p for p in fake_s3.puts if p[1] == "datasets/topics_index.json")
    index_payload = json.loads(index_put[2].decode("utf-8"))
    assert index_payload["lastPage"] == 3
    assert index_payload["pageSize"] == 1
    assert index_payload["totalTopics"] == 3
    assert index_payload["pages"] == ["page_1.json", "page_2.json", "page_3.json"]


def test_pipeline_deletes_stale_pages_when_count_shrinks(monkeypatch):
    monkeypatch.setattr(pipeline.config, "RAW_BUCKET", "raw-bucket")
    monkeypatch.setattr(pipeline.config, "CURATED_BUCKET", "curated-bucket")
    monkeypatch.setattr(pipeline.config, "TOPICS_INDEX_KEY", "datasets/topics_index.json")
    monkeypatch.setattr(pipeline.config, "TOPICS_PAGE_PREFIX", "datasets/topics/page_")
    monkeypatch.setattr(pipeline.config, "TOPICS_PAGE_SIZE", 1)
    monkeypatch.setattr(pipeline.config, "TOPICS_MAX_PAGES", 10)
    monkeypatch.setattr(pipeline.config, "APPEND_MODE", False)

    mock_records = [
        {
            "id": 1,
            "title": "T1",
            "classification": "OnlyClass",
            "century": "19th century",
            "primaryimageurl": "https://img/1",
            "imagepermissionlevel": 0,
        }
    ]
    monkeypatch.setattr(
        pipeline,
        "iter_object_records",
        lambda start_page=1, max_pages=None: iter(mock_records),
    )

    fake_s3 = FakeS3Client(
        existing_dataset=None,
        existing_topics_index={"lastPage": 4, "pageSize": 1, "pages": []},
    )
    pipeline.run_ingestion_pipeline(s3_client=fake_s3)

    deleted_keys = [k for _, k in fake_s3.deletes]
    assert sorted(deleted_keys) == [
        "datasets/topics/page_2.json",
        "datasets/topics/page_3.json",
        "datasets/topics/page_4.json",
    ]


def test_pipeline_requires_bucket_config(monkeypatch):
    monkeypatch.setattr(pipeline.config, "RAW_BUCKET", "")
    monkeypatch.setattr(pipeline.config, "CURATED_BUCKET", "curated-bucket")
    monkeypatch.setattr(
        pipeline,
        "iter_object_records",
        lambda start_page=1, max_pages=None: iter([]),
    )

    fake_s3 = FakeS3Client(existing_dataset=None)
    with pytest.raises(ValueError):
        pipeline.run_ingestion_pipeline(s3_client=fake_s3)


def test_pipeline_uses_saved_next_start_page(monkeypatch):
    monkeypatch.setattr(pipeline.config, "RAW_BUCKET", "raw-bucket")
    monkeypatch.setattr(pipeline.config, "CURATED_BUCKET", "curated-bucket")
    monkeypatch.setattr(pipeline.config, "HARVARD_MAX_PAGES", 1)

    seen = {}

    def _iter(start_page=1, max_pages=None):
        seen["start_page"] = start_page
        seen["max_pages"] = max_pages
        return iter([])

    monkeypatch.setattr(pipeline, "iter_object_records", _iter)

    fake_s3 = FakeS3Client(existing_dataset=None)
    fake_s3.ingestion_state = {"nextStartPage": 42}
    pipeline.run_ingestion_pipeline(s3_client=fake_s3)

    assert seen["start_page"] == 42
    assert seen["max_pages"] == 1
