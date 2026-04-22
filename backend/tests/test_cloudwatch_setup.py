from __future__ import annotations

from typing import Any, Dict, List

from backend.src import cloudwatch_setup as cws


class FakeCloudWatchClient:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def put_metric_alarm(self, **kwargs):
        self.calls.append(kwargs)
        return {}


def test_build_alarm_definitions(monkeypatch):
    monkeypatch.setattr(cws.config, "LAMBDA_FUNCTION_NAME", "test-fn")
    monkeypatch.setattr(cws.config, "SNS_TOPIC_ARN", "arn:aws:sns:eu-west-2:123:test")
    monkeypatch.setattr(cws.config, "DATASET_FRESHNESS_MAX_HOURS", 30)

    alarms = cws.build_alarm_definitions()
    assert len(alarms) == 2
    names = [a["AlarmName"] for a in alarms]
    assert "test-fn-errors" in names
    assert "test-fn-dataset-freshness-hours" in names
    assert all(a["ActionsEnabled"] is True for a in alarms)


def test_apply_alarms_calls_put_metric_alarm(monkeypatch):
    monkeypatch.setattr(cws.config, "LAMBDA_FUNCTION_NAME", "demo-fn")
    monkeypatch.setattr(cws.config, "SNS_TOPIC_ARN", "")
    monkeypatch.setattr(cws.config, "DATASET_FRESHNESS_MAX_HOURS", 26)

    fake = FakeCloudWatchClient()
    alarm_names = cws.apply_alarms(cloudwatch_client=fake)

    assert alarm_names == ["demo-fn-errors", "demo-fn-dataset-freshness-hours"]
    assert len(fake.calls) == 2
    assert fake.calls[0]["ActionsEnabled"] is False
    assert fake.calls[1]["Namespace"] == "ArtKnowledgeExplorer"

