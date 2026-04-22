from __future__ import annotations

from typing import Any, Dict, List

import pytest

from backend.src import harvard_object_fetcher as fetcher


class FakeResponse:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Dict[str, Any]:
        return self._payload


class FakeSession:
    def __init__(self, payloads: List[Dict[str, Any]]) -> None:
        self.payloads = payloads
        self.calls: List[Dict[str, Any]] = []
        self.idx = 0

    def get(self, url: str, params: Dict[str, Any], timeout: int) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        payload = self.payloads[self.idx]
        self.idx += 1
        return FakeResponse(payload)


def test_iter_object_pages_paginates(monkeypatch):
    monkeypatch.setattr(fetcher.config, "HARVARD_ART_API_KEY", "k")
    monkeypatch.setattr(fetcher.config, "HARVARD_API_BASE_URL", "https://api.harvardartmuseums.org")
    monkeypatch.setattr(fetcher.config, "HARVARD_PAGE_SIZE", 100)
    monkeypatch.setattr(fetcher.config, "HARVARD_MAX_PAGES", 10)

    session = FakeSession(
        [
            {"info": {"next": "yes"}, "records": [{"id": 1}]},
            {"info": {}, "records": [{"id": 2}]},
        ]
    )
    pages = list(fetcher.iter_object_pages(session=session))
    assert len(pages) == 2
    assert session.calls[0]["params"]["hasimage"] == 1
    assert session.calls[0]["params"]["fields"]
    assert session.calls[0]["params"]["page"] == 1
    assert session.calls[1]["params"]["page"] == 2


def test_iter_object_records_flattens(monkeypatch):
    monkeypatch.setattr(fetcher.config, "HARVARD_ART_API_KEY", "k")
    monkeypatch.setattr(fetcher.config, "HARVARD_PAGE_SIZE", 100)
    monkeypatch.setattr(fetcher.config, "HARVARD_MAX_PAGES", 5)

    session = FakeSession(
        [
            {"info": {"next": "yes"}, "records": [{"id": 1}, {"id": 2}]},
            {"info": {}, "records": [{"id": 3}]},
        ]
    )
    records = list(fetcher.iter_object_records(session=session))
    assert [r["id"] for r in records] == [1, 2, 3]


def test_base_params_requires_api_key(monkeypatch):
    monkeypatch.setattr(fetcher.config, "HARVARD_ART_API_KEY", "")
    with pytest.raises(ValueError):
        fetcher._base_params()

