"""Custom aiohttp web routes exposed by the unified runtime."""

from __future__ import annotations

import asyncio
import io
import logging
import urllib.parse

from aiohttp import ClientSession, ClientTimeout, web
from PIL import Image, UnidentifiedImageError

from shared.config import (
    get_emoji_max_bytes,
    get_emoji_pad_box,
    get_emoji_pad_size,
)

log = logging.getLogger("c1c.web.routes")

_ALLOWED_HOSTS = {"cdn.discordapp.com", "media.discordapp.net"}
_MIN_SIZE = 64
_MAX_SIZE = 512
_MIN_BOX = 0.2
_MAX_BOX = 0.95
_TIMEOUT = 8

try:  # Pillow >= 10
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:  # pragma: no cover - Pillow < 10
    RESAMPLE_LANCZOS = Image.LANCZOS


async def _fetch_emoji_bytes(url: str, max_bytes: int) -> bytes:
    timeout = ClientTimeout(total=_TIMEOUT)
    async with ClientSession(timeout=timeout) as session:
        try:
            async with session.get(
                url,
                allow_redirects=False,
                headers={"User-Agent": "c1c-matchmaker/emoji-pad"},
            ) as resp:
                if resp.status != 200:
                    raise web.HTTPBadGateway(text="upstream error")

                content_type = resp.headers.get("Content-Type", "").lower()
                if "image" not in content_type:
                    raise web.HTTPUnsupportedMediaType(text="unsupported media type")

                length = resp.content_length
                if length and length > max_bytes:
                    raise web.HTTPRequestEntityTooLarge(text="image too large")

                data = bytearray()
                async for chunk in resp.content.iter_chunked(65536):
                    data.extend(chunk)
                    if len(data) > max_bytes:
                        raise web.HTTPRequestEntityTooLarge(text="image too large")
                return bytes(data)
        except asyncio.TimeoutError as exc:
            raise web.HTTPGatewayTimeout(text="timeout") from exc


def mount_emoji_pad(app: web.Application) -> None:
    """Register the legacy ``/emoji-pad`` proxy route if not already mounted."""

    if app.get("_emoji_pad_mounted"):
        return

    async def handle(request: web.Request) -> web.StreamResponse:
        source_url = request.query.get("u")
        if not source_url:
            raise web.HTTPBadRequest(text="missing u")

        parsed = urllib.parse.urlparse(source_url)
        if parsed.scheme not in {"https", "http"} or parsed.hostname not in _ALLOWED_HOSTS:
            raise web.HTTPBadRequest(text="invalid source host")

        size_raw = request.query.get("s")
        try:
            size = int(size_raw) if size_raw else get_emoji_pad_size()
        except Exception:
            size = get_emoji_pad_size()
        size = max(_MIN_SIZE, min(_MAX_SIZE, size))

        box_raw = request.query.get("box")
        try:
            box = float(box_raw) if box_raw else get_emoji_pad_box()
        except Exception:
            box = get_emoji_pad_box()
        box = max(_MIN_BOX, min(_MAX_BOX, box))

        max_bytes = get_emoji_max_bytes()

        try:
            data = await _fetch_emoji_bytes(source_url, max_bytes)

            try:
                image = Image.open(io.BytesIO(data)).convert("RGBA")
            except (UnidentifiedImageError, OSError) as exc:
                raise web.HTTPUnsupportedMediaType(text="unsupported media type") from exc

            alpha = image.split()[-1]
            bbox = alpha.getbbox()
            if bbox:
                image = image.crop(bbox)

            width, height = image.size
            if width <= 0 or height <= 0:
                raise web.HTTPUnsupportedMediaType(text="unsupported media type")

            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            target = int(size * box)
            longest = max(width, height)
            scale = target / float(longest or 1)
            new_width = max(1, int(round(width * scale)))
            new_height = max(1, int(round(height * scale)))
            if new_width != width or new_height != height:
                image = image.resize((new_width, new_height), RESAMPLE_LANCZOS)

            offset = ((size - new_width) // 2, (size - new_height) // 2)
            canvas.paste(image, offset, mask=image)

            buf = io.BytesIO()
            canvas.save(buf, format="PNG")
            body = buf.getvalue()

            headers = {"Cache-Control": "public, max-age=86400"}
            return web.Response(body=body, headers=headers, content_type="image/png")
        except web.HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - unexpected failure
            log.exception("/emoji-pad processing error")
            raise web.HTTPInternalServerError(text="internal error") from exc

    app.router.add_get("/emoji-pad", handle)
    app["_emoji_pad_mounted"] = True
    log.debug("/emoji-pad route registered")
