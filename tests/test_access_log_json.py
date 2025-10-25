import asyncio
import io
import json
import logging

from aiohttp.test_utils import TestClient, TestServer

from modules.common import runtime as rt
from shared import health as healthmod


class _Buffer(io.StringIO):
    pass


def test_access_log_json_contains_fields():
    async def runner() -> None:
        healthmod.set_component("discord", False)
        buffer = _Buffer()
        handler = logging.StreamHandler(buffer)
        logging.getLogger().addHandler(handler)

        try:
            app = await rt.create_app()
            async with TestServer(app) as server:
                async with TestClient(server) as client:
                    response = await client.get("/healthz")
                    assert response.status == 200

            lines = [line for line in buffer.getvalue().splitlines() if '"logger": "access"' in line]
            assert lines, "expected at least one access log line"

            payload = json.loads(lines[-1])
            assert payload.get("logger") == "access"
            assert payload.get("method") == "GET"
            assert "ms" in payload
            assert payload.get("trace")
        finally:
            logging.getLogger().removeHandler(handler)
            healthmod.set_component("discord", False)

    asyncio.run(runner())
