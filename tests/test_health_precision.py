import asyncio

from aiohttp.test_utils import TestClient, TestServer

from modules.common import runtime as rt
from shared import health as healthmod


def test_ready_false_until_required_components_ok():
    async def runner() -> None:
        healthmod.set_component("discord", False)
        app = await rt.create_app()
        async with TestServer(app) as server:
            async with TestClient(server) as client:
                try:
                    response = await client.get("/ready")
                    data = await response.json()
                    assert response.status == 200
                    assert data["ok"] is False
                    assert data["components"]["discord"]["ok"] is False

                    healthmod.set_component("discord", True)

                    response = await client.get("/ready")
                    data = await response.json()
                    assert response.status == 200
                    assert data["ok"] is True
                    assert data["components"]["discord"]["ok"] is True
                finally:
                    healthmod.set_component("discord", False)

    asyncio.run(runner())


def test_root_includes_trace():
    async def runner() -> None:
        healthmod.set_component("discord", False)
        app = await rt.create_app()
        async with TestServer(app) as server:
            async with TestClient(server) as client:
                try:
                    response = await client.get("/")
                    payload = await response.json()
                    assert response.status == 200
                    assert isinstance(payload.get("trace"), str)
                    assert payload["trace"]
                finally:
                    healthmod.set_component("discord", False)

    asyncio.run(runner())
