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



def test_build_paginated_views_chunks_topics_in_order():
    dataset = {
        "lastUpdated": "2026-05-09T00:00:00+00:00",
        "topics": [{"id": f"t{i}", "name": f"T{i}", "count": 10 - i} for i in range(7)],
    }
    pages, index = grouping.build_paginated_views(dataset, page_size=3, max_pages=10)

    assert len(pages) == 3
    assert [p["page"] for p in pages] == [1, 2, 3]
    assert [t["id"] for t in pages[0]["topics"]] == ["t0", "t1", "t2"]
    assert [t["id"] for t in pages[2]["topics"]] == ["t6"]
    for page in pages:
        assert page["pageSize"] == 3
        assert page["totalTopics"] == 7
        assert page["lastPage"] == 3

    assert index["totalTopics"] == 7
    assert index["exposedTopics"] == 7
    assert index["pageSize"] == 3
    assert index["lastPage"] == 3
    assert index["maxPages"] == 10
    assert index["version"] == "2026-05-09T00:00:00+00:00"
    assert index["pages"] == ["page_1.json", "page_2.json", "page_3.json"]


def test_build_paginated_views_caps_at_max_pages():
    dataset = {
        "lastUpdated": "2026-05-09T00:00:00+00:00",
        "topics": [{"id": f"t{i}", "name": f"T{i}", "count": 1} for i in range(20)],
    }
    pages, index = grouping.build_paginated_views(dataset, page_size=3, max_pages=2)

    assert len(pages) == 2
    assert sum(len(p["topics"]) for p in pages) == 6
    assert index["totalTopics"] == 20
    assert index["exposedTopics"] == 6
    assert index["lastPage"] == 2


def test_build_paginated_views_empty_dataset():
    pages, index = grouping.build_paginated_views(
        {"lastUpdated": "2026-05-09T00:00:00+00:00", "topics": []},
        page_size=3,
        max_pages=10,
    )
    assert pages == []
    assert index["lastPage"] == 0
    assert index["pages"] == []
    assert index["totalTopics"] == 0
