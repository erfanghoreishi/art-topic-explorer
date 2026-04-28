"""Minimal admin Lambda for manual refresh and schedule updates."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from . import config


JsonDict = Dict[str, Any]

SCHEDULE_PRESETS: Dict[str, str] = {
    "hourly": "rate(1 hour)",
    "every_6_hours": "rate(6 hours)",
    "daily": "rate(1 day)",
}


def _response(status_code: int, body: JsonDict) -> JsonDict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "https://museum.ghoreishi.dev",
            "Access-Control-Allow-Headers": "Content-Type,x-admin-token",
            "Access-Control-Allow-Methods": "OPTIONS,POST",
        },
        "body": json.dumps(body, ensure_ascii=True),
    }


def _json_body(event: JsonDict) -> JsonDict:
    raw = event.get("body")
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _authorized(event: JsonDict) -> bool:
    token = (config.ADMIN_TOKEN or "").strip()
    if not token:
        return False
    headers = event.get("headers") or {}
    supplied = headers.get("x-admin-token") or headers.get("X-Admin-Token") or ""
    return supplied == token


def _lambda_client():
    return boto3.client("lambda", region_name=config.AWS_REGION)


def _events_client():
    return boto3.client("events", region_name=config.AWS_REGION)


def _s3_client():
    return boto3.client("s3", region_name=config.AWS_REGION)


def _state_bucket() -> str:
    bucket = (config.CURATED_BUCKET or "").strip()
    if not bucket:
        raise ValueError("CURATED_BUCKET is required for admin refresh cooldown state.")
    return bucket


def _read_refresh_state(s3_client) -> JsonDict:
    try:
        resp = s3_client.get_object(Bucket=_state_bucket(), Key=config.ADMIN_STATE_KEY)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"NoSuchKey", "404"}:
            return {}
        raise
    content = resp["Body"].read()
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    if not content:
        return {}
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


def _write_refresh_state(s3_client, state: JsonDict) -> None:
    s3_client.put_object(
        Bucket=_state_bucket(),
        Key=config.ADMIN_STATE_KEY,
        Body=json.dumps(state, ensure_ascii=True).encode("utf-8"),
        ContentType="application/json",
    )


def _enforce_cooldown(s3_client, now_epoch: int) -> Optional[int]:
    state = _read_refresh_state(s3_client)
    last = int(state.get("lastRefreshRequestEpoch", 0) or 0)
    cooldown = max(config.ADMIN_REFRESH_COOLDOWN_SECONDS, 0)
    if last <= 0 or cooldown == 0:
        return None
    delta = now_epoch - last
    if delta >= cooldown:
        return None
    return cooldown - delta


def _trigger_refresh(lambda_client, s3_client) -> JsonDict:
    now_epoch = int(time.time())
    remaining = _enforce_cooldown(s3_client, now_epoch)
    if remaining is not None:
        return _response(
            429,
            {
                "status": "cooldown",
                "message": "Refresh request is rate-limited.",
                "retryAfterSeconds": remaining,
            },
        )

    lambda_client.invoke(
        FunctionName=config.INGESTION_LAMBDA_NAME,
        InvocationType="Event",
        Payload=b"{}",
    )
    _write_refresh_state(
        s3_client,
        {
            "lastRefreshRequestEpoch": now_epoch,
            "cooldownSeconds": config.ADMIN_REFRESH_COOLDOWN_SECONDS,
        },
    )
    return _response(
        200,
        {
            "status": "accepted",
            "action": "refresh-now",
            "targetLambda": config.INGESTION_LAMBDA_NAME,
        },
    )


def _set_schedule(events_client, preset: str) -> JsonDict:
    expression = SCHEDULE_PRESETS.get(preset)
    if not expression:
        return _response(
            400,
            {
                "status": "error",
                "message": f"Unsupported schedule preset: {preset}",
                "allowedPresets": sorted(SCHEDULE_PRESETS.keys()),
            },
        )

    # Guardrail: require existing rule; avoid accidental creation typo.
    try:
        events_client.describe_rule(Name=config.EVENTBRIDGE_RULE_NAME)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"ResourceNotFoundException"}:
            return _response(
                404,
                {
                    "status": "error",
                    "message": f"EventBridge rule not found: {config.EVENTBRIDGE_RULE_NAME}",
                },
            )
        raise

    events_client.put_rule(
        Name=config.EVENTBRIDGE_RULE_NAME,
        ScheduleExpression=expression,
        State="ENABLED",
    )
    return _response(
        200,
        {
            "status": "ok",
            "action": "set-schedule",
            "ruleName": config.EVENTBRIDGE_RULE_NAME,
            "preset": preset,
            "scheduleExpression": expression,
        },
    )


def handler(event: Optional[JsonDict], context: Any) -> JsonDict:
    event = event or {}
    if not _authorized(event):
        return _response(401, {"status": "unauthorized"})

    method = (event.get("httpMethod") or "POST").upper()
    if method != "POST":
        return _response(405, {"status": "error", "message": "Only POST is supported."})

    body = _json_body(event)
    action = (body.get("action") or "").strip().lower()
    if action not in {"auth-check", "refresh-now", "set-schedule"}:
        return _response(
            400,
            {
                "status": "error",
                "message": "Invalid action.",
                "allowedActions": ["auth-check", "refresh-now", "set-schedule"],
            },
        )

    if action == "auth-check":
        return _response(200, {"status": "ok", "action": "auth-check"})

    if action == "refresh-now":
        return _trigger_refresh(_lambda_client(), _s3_client())

    preset = (body.get("preset") or "").strip()
    return _set_schedule(_events_client(), preset)
