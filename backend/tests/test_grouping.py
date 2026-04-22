from __future__ import annotations

from backend.src import grouping


def test_build_topic_tree_groups_by_classification_and_era(monkeypatch):
    monkeypatch.setattr(grouping.config, "TOP_CLASSIFICATION_LIMIT", 100)
    monkeypatch.setattr(grouping.config, "MAX_ITEMS_PER_ERA", 100)
    monkeypatch.setattr(grouping.config, "INCLUDE_UNKNOWN_ERA", True)

    records = [
        {"id": 1, "classification": "Paintings", "era": "19th century", "eraSource": "century"},
        {"id": 2, "classification": "Paintings", "era": "19th century", "eraSource": "century"},
        {"id": 3, "classification": "Prints", "era": "Unknown Era", "eraSource": "unknown"},
    ]
    out = grouping.build_topic_tree(records)
    assert out["source"]["endpoint"] == "/object"
    assert len(out["topics"]) == 2


def test_build_topic_tree_respects_caps(monkeypatch):
    monkeypatch.setattr(grouping.config, "TOP_CLASSIFICATION_LIMIT", 1)
    monkeypatch.setattr(grouping.config, "MAX_ITEMS_PER_ERA", 1)
    monkeypatch.setattr(grouping.config, "INCLUDE_UNKNOWN_ERA", True)

    records = [
        {"id": 1, "classification": "A", "era": "E1", "eraSource": "period"},
        {"id": 2, "classification": "A", "era": "E1", "eraSource": "period"},
        {"id": 3, "classification": "B", "era": "E2", "eraSource": "century"},
    ]
    out = grouping.build_topic_tree(records)
    assert len(out["topics"]) == 1
    sub = out["topics"][0]["subtopics"][0]
    assert sub["count"] == 1
    assert len(sub["items"]) == 1


def test_merge_datasets_dedupes_by_id(monkeypatch):
    monkeypatch.setattr(grouping.config, "TOP_CLASSIFICATION_LIMIT", 100)
    monkeypatch.setattr(grouping.config, "MAX_ITEMS_PER_ERA", 100)
    monkeypatch.setattr(grouping.config, "DEDUPE_BY_ID", True)
    monkeypatch.setattr(grouping.config, "INCLUDE_UNKNOWN_ERA", True)

    existing = grouping.build_topic_tree(
        [{"id": 2, "classification": "Paintings", "era": "19th century", "eraSource": "century", "title": "old"}]
    )
    incoming = grouping.build_topic_tree(
        [
            {"id": 2, "classification": "Paintings", "era": "19th century", "eraSource": "century", "title": "new"},
            {"id": 3, "classification": "Prints", "era": "Unknown Era", "eraSource": "unknown"},
        ]
    )
    merged = grouping.merge_datasets(existing, incoming)
    items = grouping.flatten_items(merged)
    by_id = {i["id"]: i for i in items}
    assert sorted(by_id.keys()) == [2, 3]
    assert by_id[2]["title"] == "new"

