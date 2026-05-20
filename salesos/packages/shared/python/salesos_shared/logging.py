import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
_SENSITIVE_KEY_FRAGMENTS = ("token", "secret", "password", "apikey", "api_key", "authorization")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_context.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            payload.update(record.extra)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_extra(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return {"extra": _sanitize_for_logging(kwargs)}


def _sanitize_for_logging(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_mapping_value(key, item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_logging(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_for_logging(item) for item in value)
    if isinstance(value, str):
        return _sanitize_url(value)
    return value


def _sanitize_mapping_value(key: str, value: Any) -> Any:
    if any(fragment in key.lower() for fragment in _SENSITIVE_KEY_FRAGMENTS):
        return "[REDACTED]"
    return _sanitize_for_logging(value)


def _sanitize_url(value: str) -> str:
    if "://" not in value or "?" not in value:
        return value
    try:
        split = urlsplit(value)
        query = parse_qsl(split.query, keep_blank_values=True)
    except ValueError:
        return value
    if not query:
        return value

    redacted: list[tuple[str, str]] = []
    changed = False
    for key, item in query:
        if any(fragment in key.lower() for fragment in _SENSITIVE_KEY_FRAGMENTS):
            redacted.append((key, "[REDACTED]"))
            changed = True
        else:
            redacted.append((key, item))
    if not changed:
        return value
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(redacted), split.fragment))
