"""Structured logging utilities for JSON-formatted runtime output."""

from __future__ import annotations

import contextvars
import json
import logging
import time
import uuid
from typing import Any, Mapping

# Context variable that carries the current trace identifier.
_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


def set_trace_id(value: str | None = None) -> str:
    """Assign a trace identifier for the current context.

    When ``value`` is ``None`` a new UUIDv4 string is generated. The identifier is
    returned so callers can reuse it when emitting log entries or HTTP responses.
    """

    trace = value or str(uuid.uuid4())
    _trace_id_var.set(trace)
    return trace


def get_trace_id() -> str:
    """Return the active trace identifier for the current context."""

    return _trace_id_var.get()


class JsonFormatter(logging.Formatter):
    """Formatter that renders log records as JSON objects."""

    def __init__(self, static: Mapping[str, Any] | None = None) -> None:
        super().__init__()
        self._static = dict(static or {})

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - docstring inherited
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "trace": getattr(record, "trace", "") or get_trace_id(),
        }

        payload.update(self._static)

        for key, value in record.__dict__.items():
            if key.startswith("_") or key in payload:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                payload[key] = value

        return json.dumps(payload, ensure_ascii=False)
