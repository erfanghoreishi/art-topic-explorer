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



def test_config_topic_pagination_defaults(monkeypatch):
    for var in ("TOPICS_INDEX_KEY", "TOPICS_PAGE_PREFIX", "TOPICS_PAGE_SIZE", "TOPICS_MAX_PAGES"):
        monkeypatch.delenv(var, raising=False)

    import backend.src.config as config

    reloaded = importlib.reload(config)
    assert reloaded.TOPICS_INDEX_KEY == "datasets/topics_index.json"
    assert reloaded.TOPICS_PAGE_PREFIX == "datasets/topics/page_"
    assert reloaded.TOPICS_PAGE_SIZE == 3
    assert reloaded.TOPICS_MAX_PAGES == 20


def test_config_topic_pagination_overrides(monkeypatch):
    monkeypatch.setenv("TOPICS_PAGE_SIZE", "6")
    monkeypatch.setenv("TOPICS_MAX_PAGES", "10")
    monkeypatch.setenv("TOPICS_INDEX_KEY", "custom/index.json")
    monkeypatch.setenv("TOPICS_PAGE_PREFIX", "custom/p_")

    import backend.src.config as config

    reloaded = importlib.reload(config)
    assert reloaded.TOPICS_PAGE_SIZE == 6
    assert reloaded.TOPICS_MAX_PAGES == 10
    assert reloaded.TOPICS_INDEX_KEY == "custom/index.json"
    assert reloaded.TOPICS_PAGE_PREFIX == "custom/p_"


def test_config_topic_pagination_clamps_to_one(monkeypatch):
    monkeypatch.setenv("TOPICS_PAGE_SIZE", "0")
    monkeypatch.setenv("TOPICS_MAX_PAGES", "-5")

    import backend.src.config as config

    reloaded = importlib.reload(config)
    assert reloaded.TOPICS_PAGE_SIZE == 1
    assert reloaded.TOPICS_MAX_PAGES == 1
