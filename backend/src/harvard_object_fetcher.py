"""Stream-style paged fetcher for Harvard Art Museums `/object`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Generator, Iterable, Optional

import requests

from . import config
from .harvard_object_contract import (
    OBJECT_ENDPOINT,
    OBJECT_HAS_IMAGE,
    OBJECT_PAGE_SIZE_MAX,
    object_fields_param,
)


JsonDict = Dict[str, Any]


@dataclass(frozen=True)
class FetchStats:
    """Summary stats from an object ingestion pull."""

    pages_fetched: int
    records_streamed: int
    stopped_reason: str


def _effective_page_size() -> int:
    return min(max(config.HARVARD_PAGE_SIZE, 1), OBJECT_PAGE_SIZE_MAX)


def _base_params() -> JsonDict:
    if not config.HARVARD_ART_API_KEY:
        raise ValueError("Missing HARVARD_ART_API_KEY in environment.")

    return {
        "apikey": config.HARVARD_ART_API_KEY,
        "hasimage": OBJECT_HAS_IMAGE,
        "fields": object_fields_param(),
        "size": _effective_page_size(),
    }


def iter_object_pages(
    session: Optional[requests.Session] = None,
    start_page: int = 1,
    max_pages: Optional[int] = None,
    timeout_seconds: int = 30,
) -> Generator[JsonDict, None, FetchStats]:
    """
    Yield `/object` response pages as dictionaries.

    Stops when one of the following occurs:
    - no `next` URL exists in response `info`
    - max_pages is reached
    - API returns zero records
    """
    effective_max_pages = max_pages if max_pages is not None else config.HARVARD_MAX_PAGES
    page = max(start_page, 1)
    pages_fetched = 0
    records_streamed = 0

    active_session = session or requests.Session()
    close_when_done = session is None

    stopped_reason = "unknown"
    try:
        while pages_fetched < effective_max_pages:
            params = _base_params()
            params["page"] = page
            url = f"{config.HARVARD_API_BASE_URL.rstrip('/')}{OBJECT_ENDPOINT}"
            response = active_session.get(url, params=params, timeout=timeout_seconds)
            response.raise_for_status()
            payload = response.json()

            records = payload.get("records") or []
            info = payload.get("info") or {}

            pages_fetched += 1
            records_streamed += len(records)
            yield payload

            if not records:
                stopped_reason = "empty_records"
                break
            if not info.get("next"):
                stopped_reason = "no_next_page"
                break
            page += 1
        else:
            stopped_reason = "max_pages_reached"
    finally:
        if close_when_done:
            active_session.close()

    return FetchStats(
        pages_fetched=pages_fetched,
        records_streamed=records_streamed,
        stopped_reason=stopped_reason,
    )


def iter_object_records(
    session: Optional[requests.Session] = None,
    start_page: int = 1,
    max_pages: Optional[int] = None,
    timeout_seconds: int = 30,
) -> Iterable[JsonDict]:
    """Yield one `/object` record at a time across paged API responses."""
    page_iter = iter_object_pages(
        session=session,
        start_page=start_page,
        max_pages=max_pages,
        timeout_seconds=timeout_seconds,
    )
    for payload in page_iter:
        for record in payload.get("records") or []:
            yield record

