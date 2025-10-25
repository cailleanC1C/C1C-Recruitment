import asyncio
import io

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from PIL import Image

from shared import web_routes


def _png_bytes() -> bytes:
    image = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_emoji_proxy_rejects_http():
    async def runner() -> None:
        app = web.Application()
        web_routes.mount_emoji_pad(app)

        async with TestServer(app) as server:
            async with TestClient(server) as client:
                resp = await client.get(
                    "/emoji-pad",
                    params={"u": "http://cdn.discordapp.com/emojis/123.png"},
                )
                assert resp.status == 400

    asyncio.run(runner())


def test_emoji_proxy_allows_https(monkeypatch):
    async def runner() -> None:
        app = web.Application()
        web_routes.mount_emoji_pad(app)

        png_data = _png_bytes()

        async def fake_fetch(session, url, max_bytes):
            assert url.startswith("https://")
            return png_data

        monkeypatch.setattr(web_routes, "_fetch_emoji_bytes", fake_fetch)

        async with TestServer(app) as server:
            async with TestClient(server) as client:
                resp = await client.get(
                    "/emoji-pad",
                    params={"u": "https://cdn.discordapp.com/emojis/123.png"},
                )
                assert resp.status == 200
                body = await resp.read()
                assert body.startswith(b"\x89PNG")

    asyncio.run(runner())
