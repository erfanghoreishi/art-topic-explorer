"""Step 9: local end-to-end dry run for demo preparation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from . import config
from .grouping import build_topic_tree
from .harvard_object_fetcher import iter_object_records
from .normalizer import normalize_object_record


JsonDict = Dict[str, Any]


def run_local_demo_dataset(max_pages: int | None = None) -> JsonDict:
    """
    Generate a local dataset JSON from live Harvard `/object` records.

    Output path defaults to config.LOCAL_DEMO_DATASET_PATH.
    """
    raw_records: List[JsonDict] = []
    normalized_records: List[JsonDict] = []

    for record in iter_object_records(max_pages=max_pages):
        raw_records.append(record)
        normalized = normalize_object_record(record)
        if normalized:
            normalized_records.append(normalized)

    dataset = build_topic_tree(normalized_records)
    output_path = Path(config.LOCAL_DEMO_DATASET_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dataset, ensure_ascii=True, indent=2), encoding="utf-8")

    return {
        "rawRecordsCount": len(raw_records),
        "normalizedRecordsCount": len(normalized_records),
        "topicsCount": len(dataset.get("topics", [])),
        "outputPath": str(output_path),
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description="Generate local frontend dataset for demo.")
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

