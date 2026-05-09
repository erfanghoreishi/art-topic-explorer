"""Step 9: local end-to-end dry run for demo preparation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from . import config
from .grouping import build_paginated_views, build_topic_tree
from .harvard_object_fetcher import iter_object_records
from .normalizer import normalize_object_record


JsonDict = Dict[str, Any]


def run_local_demo_dataset(max_pages: int | None = None) -> JsonDict:
    """
    Generate a local dataset JSON from live Harvard `/object` records.

    Also writes paginated topic files to frontend/topics/ directory.
    Output paths default to config.LOCAL_DEMO_DATASET_PATH and frontend/topics/.
    """
    raw_records: List[JsonDict] = []
    normalized_records: List[JsonDict] = []

    for record in iter_object_records(max_pages=max_pages):
        raw_records.append(record)
        normalized = normalize_object_record(record)
        if normalized:
            normalized_records.append(normalized)

    dataset = build_topic_tree(normalized_records)

    # Write legacy dataset.json
    output_path = Path(config.LOCAL_DEMO_DATASET_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(
        dataset, ensure_ascii=True, indent=2), encoding="utf-8")

    # Write paginated views (topics_index.json + topics/page_<n>.json)
    pages, index = build_paginated_views(
        dataset,
        page_size=config.TOPICS_PAGE_SIZE,
        max_pages=config.TOPICS_MAX_PAGES,
    )

    topics_dir = output_path.parent / "topics"
    topics_dir.mkdir(parents=True, exist_ok=True)

    index_path = output_path.parent / "topics_index.json"
    index_path.write_text(json.dumps(
        index, ensure_ascii=True, indent=2), encoding="utf-8")

    for page_data in pages:
        page_num = page_data["page"]
        page_path = topics_dir / f"page_{page_num}.json"
        page_path.write_text(json.dumps(
            page_data, ensure_ascii=True, indent=2), encoding="utf-8")

    return {
        "rawRecordsCount": len(raw_records),
        "normalizedRecordsCount": len(normalized_records),
        "topicsCount": len(dataset.get("topics", [])),
        "datasetPath": str(output_path),
        "topicsIndexPath": str(index_path),
        "topicsPagesCount": len(pages),
    }


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate local frontend dataset for demo.")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional page cap for faster demo generation.",
    )
    args = parser.parse_args()
    result = run_local_demo_dataset(max_pages=args.max_pages)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
