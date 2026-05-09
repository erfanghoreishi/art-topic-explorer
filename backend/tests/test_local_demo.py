from __future__ import annotations

import json
from pathlib import Path

from backend.src import local_demo


def test_run_local_demo_dataset_writes_output(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        local_demo.config,
        "LOCAL_DEMO_DATASET_PATH",
        str(tmp_path / "frontend" / "dataset.json"),
    )

    records = [
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
    monkeypatch.setattr(local_demo, "iter_object_records", lambda max_pages=None: iter(records))

    result = local_demo.run_local_demo_dataset(max_pages=1)
    assert result["rawRecordsCount"] == 2
    assert result["normalizedRecordsCount"] == 2
    assert result["topicsCount"] >= 1

    output_file = Path(result["datasetPath"])
    assert output_file.exists()
    loaded = json.loads(output_file.read_text(encoding="utf-8"))
    assert "topics" in loaded

    index_file = Path(result["topicsIndexPath"])
    assert index_file.exists()
    index_payload = json.loads(index_file.read_text(encoding="utf-8"))
    assert index_payload["totalTopics"] == loaded["topics"].__len__()
    assert result["topicsPagesCount"] == index_payload["lastPage"]

    for n in range(1, result["topicsPagesCount"] + 1):
        page_file = output_file.parent / "topics" / f"page_{n}.json"
        assert page_file.exists()

