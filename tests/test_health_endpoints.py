import asyncio

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from modules.common import runtime as rt


class DummyBot:
    """Minimal bot stub for runtime wiring."""

    async def wait_until_ready(self) -> None:  # pragma: no cover - defensive stub
        return None

    def get_channel(self, _channel_id):  # pragma: no cover - defensive stub
        return None

    async def fetch_channel(self, _channel_id):  # pragma: no cover - defensive stub
        raise RuntimeError("not implemented")


class _DummyRunner:
    def __init__(self, app: web.Application) -> None:
        self.app = app

    async def setup(self) -> None:  # pragma: no cover - no side effects in tests
        return None

    async def cleanup(self) -> None:  # pragma: no cover - no side effects in tests
        return None


class _DummySite:
    def __init__(self, runner: _DummyRunner, host: str, port: int) -> None:
        self.runner = runner
        self.host = host
        self.port = port
        self.started = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.started = False


def test_health_endpoints_exist_and_return_json(monkeypatch):
    async def runner() -> None:
        monkeypatch.setattr(rt.web, "AppRunner", _DummyRunner)
        monkeypatch.setattr(rt.web, "TCPSite", _DummySite)

        runtime = rt.Runtime(bot=DummyBot())
        await runtime.start_webserver(port=0)
        try:
            app = runtime._web_app
            assert app is not None

            async with TestServer(app) as server:
                async with TestClient(server) as client:
                    resp = await client.get("/")
                    assert resp.status == 200
                    data = await resp.json()
                    assert data.get("ok") is True
                    assert "bot" in data and "env" in data and "version" in data

                    for path in ("/health", "/healthz", "/ready"):
                        resp = await client.get(path)
                        assert resp.status == 200
                        payload = await resp.json()
                        assert payload.get("ok") is True
        finally:
            await runtime.shutdown_webserver()

    asyncio.run(runner())
