"""Configuration for the 1-day Harvard Topic Explorer MVP."""

from __future__ import annotations

import os
from dotenv import load_dotenv

# Load .env file into environment
load_dotenv()


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name, str(default))
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {name} must be an integer, got: {value}") from exc


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


HARVARD_ART_API_KEY = os.getenv("HARVARD_ART_API_KEY", "")
HARVARD_API_BASE_URL = os.getenv(
    "HARVARD_API_BASE_URL", "https://api.harvardartmuseums.org")

HARVARD_PAGE_SIZE = _get_int("HARVARD_PAGE_SIZE", 100)
HARVARD_MAX_PAGES = _get_int("HARVARD_MAX_PAGES", 20)
INGESTION_START_PAGE = _get_int("INGESTION_START_PAGE", 1)
TOP_CLASSIFICATION_LIMIT = _get_int("TOP_CLASSIFICATION_LIMIT", 12)
MAX_ITEMS_PER_ERA = _get_int("MAX_ITEMS_PER_ERA", 24)
INCLUDE_UNKNOWN_ERA = _get_bool("INCLUDE_UNKNOWN_ERA", True)
APPEND_MODE = _get_bool("APPEND_MODE", True)
DEDUPE_BY_ID = _get_bool("DEDUPE_BY_ID", True)

AWS_REGION = os.getenv("AWS_REGION", "eu-west-2")
RAW_BUCKET = os.getenv("RAW_BUCKET", "")
CURATED_BUCKET = os.getenv("CURATED_BUCKET", "")
RAW_KEY = os.getenv("RAW_KEY", "raw/objects.jsonl")
DATASET_KEY = os.getenv("DATASET_KEY", "datasets/topic_tree.json")
TOPICS_INDEX_KEY = os.getenv("TOPICS_INDEX_KEY", "datasets/topics_index.json")
TOPICS_PAGE_PREFIX = os.getenv("TOPICS_PAGE_PREFIX", "datasets/topics/page_")
TOPICS_PAGE_SIZE = max(_get_int("TOPICS_PAGE_SIZE", 3), 1)
TOPICS_MAX_PAGES = max(_get_int("TOPICS_MAX_PAGES", 20), 1)
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "")
LAMBDA_FUNCTION_NAME = os.getenv(
    "LAMBDA_FUNCTION_NAME", "ham-topic-explorer-ingestion")
DATASET_FRESHNESS_MAX_HOURS = _get_int("DATASET_FRESHNESS_MAX_HOURS", 26)
LOCAL_DEMO_DATASET_PATH = os.getenv(
    "LOCAL_DEMO_DATASET_PATH", "frontend/dataset.json")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
EVENTBRIDGE_RULE_NAME = os.getenv(
    "EVENTBRIDGE_RULE_NAME", "ham-topic-explorer-refresh")
INGESTION_LAMBDA_NAME = os.getenv(
    "INGESTION_LAMBDA_NAME", LAMBDA_FUNCTION_NAME)
ADMIN_REFRESH_COOLDOWN_SECONDS = _get_int(
    "ADMIN_REFRESH_COOLDOWN_SECONDS", 300)
ADMIN_STATE_KEY = os.getenv("ADMIN_STATE_KEY", "admin/refresh_state.json")
INGESTION_STATE_KEY = os.getenv(
    "INGESTION_STATE_KEY", "admin/ingestion_state.json")
