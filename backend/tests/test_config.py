from __future__ import annotations

import importlib


def test_config_reads_env_values(monkeypatch):
    monkeypatch.setenv("HARVARD_ART_API_KEY", "k")
    monkeypatch.setenv("HARVARD_PAGE_SIZE", "77")
    monkeypatch.setenv("APPEND_MODE", "true")
    monkeypatch.setenv("DEDUPE_BY_ID", "false")

    import backend.src.config as config

    reloaded = importlib.reload(config)
    assert reloaded.HARVARD_ART_API_KEY == "k"
    assert reloaded.HARVARD_PAGE_SIZE == 77
    assert reloaded.APPEND_MODE is True
    assert reloaded.DEDUPE_BY_ID is False


def test_config_invalid_int_raises(monkeypatch):
    monkeypatch.setenv("HARVARD_PAGE_SIZE", "not-an-int")

    import backend.src.config as config

    try:
        importlib.reload(config)
        raised = False
    except ValueError as exc:
        raised = True
        assert "HARVARD_PAGE_SIZE" in str(exc)
    assert raised

