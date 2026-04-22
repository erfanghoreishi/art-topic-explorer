"""Step 7: minimal CloudWatch alarm setup for the ingestion pipeline."""

from __future__ import annotations

from typing import Any, Dict, List

import boto3

from . import config


JsonDict = Dict[str, Any]


def _cloudwatch_client():
    return boto3.client("cloudwatch", region_name=config.AWS_REGION)


def _alarm_actions() -> List[str]:
    topic = (config.SNS_TOPIC_ARN or "").strip()
    return [topic] if topic else []


def build_alarm_definitions() -> List[JsonDict]:
    """Return day-one CloudWatch alarm definitions."""
    prefix = config.LAMBDA_FUNCTION_NAME

    lambda_errors_alarm: JsonDict = {
        "AlarmName": f"{prefix}-errors",
        "AlarmDescription": "Triggers when ingestion Lambda reports any Errors in a 5-minute window.",
        "Namespace": "AWS/Lambda",
        "MetricName": "Errors",
        "Dimensions": [{"Name": "FunctionName", "Value": config.LAMBDA_FUNCTION_NAME}],
        "Statistic": "Sum",
        "Period": 300,
        "EvaluationPeriods": 1,
        "DatapointsToAlarm": 1,
        "Threshold": 1.0,
        "ComparisonOperator": "GreaterThanOrEqualToThreshold",
        "TreatMissingData": "notBreaching",
        "ActionsEnabled": bool(_alarm_actions()),
        "AlarmActions": _alarm_actions(),
        "OKActions": _alarm_actions(),
    }

    freshness_alarm: JsonDict = {
        "AlarmName": f"{prefix}-dataset-freshness-hours",
        "AlarmDescription": (
            "Triggers when custom metric ArtKnowledgeExplorer/DatasetAgeHours "
            f"exceeds {config.DATASET_FRESHNESS_MAX_HOURS} hours."
        ),
        "Namespace": "ArtKnowledgeExplorer",
        "MetricName": "DatasetAgeHours",
        "Dimensions": [{"Name": "Pipeline", "Value": "harvard-topic-explorer"}],
        "Statistic": "Maximum",
        "Period": 3600,
        "EvaluationPeriods": 1,
        "DatapointsToAlarm": 1,
        "Threshold": float(config.DATASET_FRESHNESS_MAX_HOURS),
        "ComparisonOperator": "GreaterThanThreshold",
        "TreatMissingData": "notBreaching",
        "ActionsEnabled": bool(_alarm_actions()),
        "AlarmActions": _alarm_actions(),
        "OKActions": _alarm_actions(),
    }
    return [lambda_errors_alarm, freshness_alarm]


def apply_alarms(cloudwatch_client=None) -> List[str]:
    """Create or update configured alarms. Returns alarm names."""
    client = cloudwatch_client or _cloudwatch_client()
    alarms = build_alarm_definitions()
    for alarm in alarms:
        client.put_metric_alarm(**alarm)
    return [a["AlarmName"] for a in alarms]

