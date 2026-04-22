from __future__ import annotations

import os

import pytest

from backend.src import harvard_object_fetcher as fetcher
from backend.src.normalizer import normalize_object_record


RUN_REAL = os.getenv("RUN_REAL_API_TESTS", "").lower() in {"1", "true", "yes"}


@pytest.mark.skipif(not RUN_REAL, reason="Set RUN_REAL_API_TESTS=true to run live Harvard API test.")
def test_real_api_single_page_smoke(monkeypatch):
    api_key = os.getenv("HARVARD_ART_API_KEY", "").strip()
    if not api_key:
        pytest.skip("HARVARD_ART_API_KEY is required for real API test.")

    monkeypatch.setattr(fetcher.config, "HARVARD_ART_API_KEY", api_key)

    pages = list(fetcher.iter_object_pages(max_pages=1))
    assert len(pages) == 1
    payload = pages[0]
    assert "info" in payload
    assert "records" in payload


    if payload["records"]:
        normalized = normalize_object_record(payload["records"][0])
        # At least ensure normalizer can process a real record shape.

        assert normalized is None or "id" in normalized
