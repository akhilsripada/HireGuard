"""Shared helpers for the Lambda handlers: responses, input parsing, AWS clients, logging."""
import base64
import json
import logging
import os
import time
from functools import lru_cache
from typing import Any

log = logging.getLogger("hireguard")
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# boto3 is imported lazily so the handlers also run locally (run.py) without it installed.
_table_override = None


def fast_config():
    """Short timeouts and no retries for AWS calls on the request path."""
    from botocore.config import Config

    return Config(connect_timeout=1, read_timeout=float(os.environ.get("EXTERNAL_TIMEOUT_S", "1.5")), retries={"max_attempts": 1})


def use_tables(factory) -> None:
    """Swap DynamoDB for another table implementation (local mode and tests). None restores DynamoDB."""
    global _table_override
    _table_override = factory
    _dynamo_table.cache_clear()


class BadRequest(Exception):
    """Client sent something we can't accept. Message is safe to show to the user."""


def response(status: int, body: Any) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(body),
    }


def parse_json_body(event: dict) -> dict:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8", errors="replace")
    if len(raw) > 20_000:
        raise BadRequest("Request is too large.")
    try:
        body = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise BadRequest("Request body must be JSON.") from exc
    if not isinstance(body, dict):
        raise BadRequest("Request body must be a JSON object.")
    return body


def log_event(event_name: str, **fields: Any) -> None:
    """Structured log line. Never pass message text or contacts here."""
    log.info(json.dumps({"event": event_name, **fields}))


def table(env_name: str):
    if _table_override is not None:
        return _table_override(env_name)
    return _dynamo_table(env_name)


@lru_cache(maxsize=None)
def _dynamo_table(env_name: str):
    import boto3

    return boto3.resource("dynamodb").Table(os.environ[env_name])


@lru_cache(maxsize=None)
def secret_value(arn: str) -> dict:
    """Read once per cold start; secrets never reach logs."""
    import boto3

    raw = boto3.client("secretsmanager").get_secret_value(SecretId=arn)["SecretString"]
    return json.loads(raw)


def now_ms() -> int:
    return int(time.time() * 1000)
