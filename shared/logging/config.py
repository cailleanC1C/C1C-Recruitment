"""Runtime logging configuration utilities."""

from __future__ import annotations

import logging
from typing import Mapping

from .structured import JsonFormatter

__all__ = ["setup_logging"]


def _ensure_stream_handler(logger: logging.Logger, formatter: logging.Formatter) -> None:
    """Ensure ``logger`` has a stream handler using ``formatter``."""

    stream_handler_found = False
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setFormatter(formatter)
            stream_handler_found = True
    if not stream_handler_found:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)


def setup_logging(
    *,
    static_fields: Mapping[str, str] | None = None,
    access_logger_name: str = "aiohttp.access",
    access_static_fields: Mapping[str, str] | None = None,
) -> logging.Logger:
    """Configure JSON logging for the runtime.

    Parameters
    ----------
    static_fields:
        Base static fields included with every structured log event.
    access_logger_name:
        Name of the access logger that should emit HTTP request entries.
    access_static_fields:
        Additional static fields for the access logger; merged with
        ``static_fields``.

    Returns
    -------
    logging.Logger
        The configured access logger instance.
    """

    base_static = dict(static_fields or {})

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    _ensure_stream_handler(root_logger, JsonFormatter(static=base_static))

    access_static = dict(base_static)
    access_static.update(access_static_fields or {})
    access_static.setdefault("logger", access_logger_name)

    access_logger = logging.getLogger(access_logger_name)
    access_logger.propagate = False
    access_logger.handlers.clear()

    access_handler = logging.StreamHandler()
    access_handler.setFormatter(JsonFormatter(static=access_static))
    access_logger.addHandler(access_handler)
    access_logger.setLevel(logging.INFO)

    return access_logger
