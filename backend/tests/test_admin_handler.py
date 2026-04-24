from __future__ import annotations

import json
from typing import Any, Dict, Optional

from botocore.exceptions import ClientError

from backend.src import admin_handler as ah


def _event(body: Dict[str, Any], token: Optional[str] = "secret") -> Dict[str, Any]:
    headers = {}
    if token is not None:
        headers["x-admin-token"] = token
    return {"httpMethod": "POST", "headers": headers, "body": json.dumps(body)}


class FakeLambdaClient:
    def __init__(self) -> None:
        self.invocations = []

    def invoke(self, **kwargs):
        self.invocations.append(kwargs)
        return {"StatusCode": 202}


class FakeS3Client:
    def __init__(self, state: Optional[Dict[str, Any]] = None) -> None:
        self.state = state
        self.puts = []

    def get_object(self, Bucket: str, Key: str):
        if self.state is None:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": FakeBody(json.dumps(self.state))}

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        self.state = json.loads(kwargs["Body"].decode("utf-8"))
        return {"ETag": "ok"}


class FakeBody:
    def __init__(self, content: str) -> None:
        self._content = content

    def read(self) -> bytes:
        return self._content.encode("utf-8")


class FakeEventsClient:
    def __init__(self, rule_exists: bool = True) -> None:
        self.rule_exists = rule_exists
        self.put_calls = []

    def describe_rule(self, Name: str):
        if not self.rule_exists:
            raise ClientError({"Error": {"Code": "ResourceNotFoundException"}}, "DescribeRule")
        return {"Name": Name}

    def put_rule(self, **kwargs):
        self.put_calls.append(kwargs)
        return {"RuleArn": "arn:rule"}


def _body(resp):
    return json.loads(resp["body"])


def test_unauthorized_request(monkeypatch):
    monkeypatch.setattr(ah.config, "ADMIN_TOKEN", "secret")
    resp = ah.handler(_event({"action": "refresh-now"}, token="wrong"), None)
    assert resp["statusCode"] == 401


def test_refresh_now_success(monkeypatch):
    fake_lambda = FakeLambdaClient()
    fake_s3 = FakeS3Client(state=None)
    monkeypatch.setattr(ah.config, "ADMIN_TOKEN", "secret")
    monkeypatch.setattr(ah.config, "CURATED_BUCKET", "bucket")
    monkeypatch.setattr(ah.config, "INGESTION_LAMBDA_NAME", "ingestion-fn")
    monkeypatch.setattr(ah.config, "ADMIN_REFRESH_COOLDOWN_SECONDS", 300)
    monkeypatch.setattr(ah, "_lambda_client", lambda: fake_lambda)
    monkeypatch.setattr(ah, "_s3_client", lambda: fake_s3)

    resp = ah.handler(_event({"action": "refresh-now"}), None)
    parsed = _body(resp)
    assert resp["statusCode"] == 200
    assert parsed["status"] == "accepted"
    assert len(fake_lambda.invocations) == 1
    assert fake_lambda.invocations[0]["FunctionName"] == "ingestion-fn"
    assert len(fake_s3.puts) == 1


def test_refresh_now_cooldown(monkeypatch):
    fake_lambda = FakeLambdaClient()
    fake_s3 = FakeS3Client(state={"lastRefreshRequestEpoch": 9999999999})
    monkeypatch.setattr(ah.config, "ADMIN_TOKEN", "secret")
    monkeypatch.setattr(ah.config, "CURATED_BUCKET", "bucket")
    monkeypatch.setattr(ah.config, "ADMIN_REFRESH_COOLDOWN_SECONDS", 300)
    monkeypatch.setattr(ah, "_lambda_client", lambda: fake_lambda)
    monkeypatch.setattr(ah, "_s3_client", lambda: fake_s3)

    resp = ah.handler(_event({"action": "refresh-now"}), None)
    parsed = _body(resp)
    assert resp["statusCode"] == 429
    assert parsed["status"] == "cooldown"
    assert len(fake_lambda.invocations) == 0


def test_set_schedule_success(monkeypatch):
    fake_events = FakeEventsClient(rule_exists=True)
    monkeypatch.setattr(ah.config, "ADMIN_TOKEN", "secret")
    monkeypatch.setattr(ah.config, "EVENTBRIDGE_RULE_NAME", "refresh-rule")
    monkeypatch.setattr(ah, "_events_client", lambda: fake_events)

    resp = ah.handler(_event({"action": "set-schedule", "preset": "daily"}), None)
    parsed = _body(resp)
    assert resp["statusCode"] == 200
    assert parsed["scheduleExpression"] == "rate(1 day)"
    assert len(fake_events.put_calls) == 1


def test_set_schedule_rejects_invalid_preset(monkeypatch):
    fake_events = FakeEventsClient(rule_exists=True)
    monkeypatch.setattr(ah.config, "ADMIN_TOKEN", "secret")
    monkeypatch.setattr(ah, "_events_client", lambda: fake_events)

    resp = ah.handler(_event({"action": "set-schedule", "preset": "every-minute"}), None)
    assert resp["statusCode"] == 400


def test_auth_check_success(monkeypatch):
    monkeypatch.setattr(ah.config, "ADMIN_TOKEN", "secret")
    resp = ah.handler(_event({"action": "auth-check"}), None)
    parsed = _body(resp)
    assert resp["statusCode"] == 200
    assert parsed["status"] == "ok"
    assert parsed["action"] == "auth-check"
