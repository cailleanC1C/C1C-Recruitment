import asyncio
import logging
from typing import List

from aiohttp.test_utils import TestClient, TestServer

from modules.common import runtime as rt
from shared import health as healthmod
from shared.logging.structured import JsonFormatter


class _Collector(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: List[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - trivial
        self.records.append(record)


def test_access_log_json_contains_fields():
    healthmod.set_component("discord", False)

    async def runner() -> tuple[list[logging.LogRecord], str | None]:
        app = await rt.create_app()
        access_logger = logging.getLogger("aiohttp.access")
        collector = _Collector()
        access_logger.addHandler(collector)
        try:
            async with TestServer(app) as server:
                async with TestClient(server) as client:
                    response = await client.get("/healthz")
                    assert response.status == 200
                    header = response.headers.get("X-Trace-Id")
            return list(collector.records), header
        finally:
            access_logger.removeHandler(collector)

    try:
        records, trace_header = asyncio.run(runner())
    finally:
        healthmod.set_component("discord", False)

    assert trace_header

    http_records = [record for record in records if record.getMessage() == "http_request"]
    assert http_records, "expected middleware http_request log"

    record = http_records[-1]
    assert record.name == "aiohttp.access"
    assert record.method == "GET"
    assert record.path == "/healthz"
    assert record.status == 200
    assert hasattr(record, "ms")
    assert getattr(record, "trace", "")

    access_logger = logging.getLogger("aiohttp.access")
    assert not access_logger.propagate
    assert access_logger.handlers, "expected access logger to have handlers"
    for handler in access_logger.handlers:
        assert isinstance(handler.formatter, JsonFormatter)
        assert handler.level in (logging.NOTSET, logging.INFO)
