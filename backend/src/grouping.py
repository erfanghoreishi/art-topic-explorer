"""Build and merge topic tree datasets: classification -> era -> artwork."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple

from . import config


JsonDict = Dict[str, Any]


def _topic_id(classification: str) -> str:
    return f"classification:{classification}"


def _era_id(era: str) -> str:
    return f"era:{era}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_unknown_era(era_name: str) -> bool:
    return era_name.strip().lower() == "unknown era"


def _sorted_topics(topics: List[JsonDict]) -> List[JsonDict]:
    return sorted(topics, key=lambda t: (-int(t.get("count", 0)), t.get("name", "")))


def _sorted_eras(eras: List[JsonDict]) -> List[JsonDict]:
    return sorted(eras, key=lambda e: (-int(e.get("count", 0)), e.get("name", "")))


def _apply_caps(dataset: JsonDict) -> JsonDict:
    """Apply day-one caps after build/merge."""
    topics = _sorted_topics(dataset.get("topics", []))
    if config.TOP_CLASSIFICATION_LIMIT > 0:
        topics = topics[: config.TOP_CLASSIFICATION_LIMIT]

    for topic in topics:
        subtopics = _sorted_eras(topic.get("subtopics", []))
        for subtopic in subtopics:
            items = subtopic.get("items", [])
            items = sorted(items, key=lambda i: i.get("id", 0))
            if config.MAX_ITEMS_PER_ERA > 0:
                items = items[: config.MAX_ITEMS_PER_ERA]
            subtopic["items"] = items
            subtopic["count"] = len(items)
        topic["subtopics"] = subtopics
        topic["count"] = sum(s.get("count", 0) for s in subtopics)

    dataset["topics"] = _sorted_topics(topics)
    dataset["lastUpdated"] = _now_iso()
    return dataset


def build_topic_tree(records: Iterable[JsonDict]) -> JsonDict:
    """
    Build a topic tree dataset from normalized records.

    Input records are expected to contain:
    - id, classification, era, eraSource, ...
    """
    # classification -> era -> items
    tree: Dict[str, Dict[Tuple[str, str], List[JsonDict]]] = defaultdict(lambda: defaultdict(list))

    for record in records:
        classification = (record.get("classification") or "Unknown Classification").strip()
        era = (record.get("era") or "Unknown Era").strip()
        era_source = (record.get("eraSource") or "unknown").strip().lower()

        if _is_unknown_era(era) and not config.INCLUDE_UNKNOWN_ERA:
            continue

        tree[classification][(era, era_source)].append(record)

    topics: List[JsonDict] = []
    for classification, era_map in tree.items():
        subtopics: List[JsonDict] = []
        for (era_name, era_source), items in era_map.items():
            subtopics.append(
                {
                    "id": _era_id(era_name),
                    "name": era_name,
                    "eraSource": era_source,
                    "count": len(items),
                    "items": items,
                }
            )

        topics.append(
            {
                "id": _topic_id(classification),
                "name": classification,
                "count": sum(s["count"] for s in subtopics),
                "subtopics": subtopics,
            }
        )

    dataset = {
        "topics": topics,
        "lastUpdated": _now_iso(),
        "source": {
            "endpoint": "/object",
            "filters": {"hasimage": 1},
        },
    }
    return _apply_caps(dataset)


def flatten_items(dataset: JsonDict) -> List[JsonDict]:
    """Return all artwork items from a dataset."""
    items: List[JsonDict] = []
    for topic in dataset.get("topics", []):
        for subtopic in topic.get("subtopics", []):
            items.extend(subtopic.get("items", []))
    return items


def build_paginated_views(
    dataset: JsonDict,
    page_size: int,
    max_pages: int,
) -> Tuple[List[JsonDict], JsonDict]:
    """Slice dataset['topics'] (already sorted/capped) into per-page payloads + an index manifest.

    Returns (page_payloads, index_payload). Topics beyond page_size*max_pages are not exposed
    via pages, but totalTopics in the index reflects the full dataset.
    """
    page_size = max(int(page_size), 1)
    max_pages = max(int(max_pages), 1)

    topics = list(dataset.get("topics", []))
    total_topics = len(topics)
    exposed = topics[: page_size * max_pages]

    pages: List[JsonDict] = []
    if exposed:
        last_page = (len(exposed) + page_size - 1) // page_size
    else:
        last_page = 0

    for page_num in range(1, last_page + 1):
        start = (page_num - 1) * page_size
        chunk = exposed[start : start + page_size]
        pages.append(
            {
                "page": page_num,
                "pageSize": page_size,
                "totalTopics": total_topics,
                "lastPage": last_page,
                "topics": chunk,
            }
        )

    last_updated = dataset.get("lastUpdated") or _now_iso()
    index = {
        "lastUpdated": last_updated,
        "totalTopics": total_topics,
        "exposedTopics": len(exposed),
        "pageSize": page_size,
        "lastPage": last_page,
        "maxPages": max_pages,
        "version": last_updated,
        "pages": [f"page_{n}.json" for n in range(1, last_page + 1)],
    }
    return pages, index


def merge_datasets(existing: JsonDict, incoming: JsonDict) -> JsonDict:
    """
    Merge two datasets in append mode.

    Dedupes by artwork id when configured; incoming wins on collision.
    """
    existing_items = flatten_items(existing)
    incoming_items = flatten_items(incoming)

    if not config.DEDUPE_BY_ID:
        merged_items = existing_items + incoming_items
        return build_topic_tree(merged_items)

    by_id: Dict[int, JsonDict] = {}
    for item in existing_items:
        item_id = item.get("id")
        if isinstance(item_id, int):
            by_id[item_id] = item
    for item in incoming_items:
        item_id = item.get("id")
        if isinstance(item_id, int):
            by_id[item_id] = item

    merged_items = list(by_id.values())
    return build_topic_tree(merged_items)

