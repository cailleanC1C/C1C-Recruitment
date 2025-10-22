"""Emoji lookup and thumbnail helpers for recruitment embeds and views."""

from __future__ import annotations

import io
import logging
import urllib.parse
from typing import Tuple

import discord
from discord.utils import get
from PIL import Image

from shared.config import (
    get_emoji_pad_box,
    get_emoji_pad_size,
    get_public_base_url,
    get_render_external_url,
    get_strict_emoji_proxy,
    get_tag_badge_box,
    get_tag_badge_px,
)

log = logging.getLogger("c1c.recruitment.emoji")

try:  # Pillow >= 10
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:  # pragma: no cover - Pillow < 10
    RESAMPLE_LANCZOS = Image.LANCZOS


def _proxy_base_url() -> str | None:
    base = get_public_base_url()
    if base:
        return base.rstrip("/")
    fallback = get_render_external_url()
    return fallback.rstrip("/") if fallback else None


def emoji_for_tag(guild: discord.Guild | None, tag: str | None) -> discord.Emoji | None:
    """Return the guild emoji matching *tag*, or ``None`` when unavailable."""

    if not guild or not tag:
        return None
    text = str(tag).strip()
    if not text:
        return None
    return get(guild.emojis, name=text)


def padded_emoji_url(
    guild: discord.Guild | None,
    tag: str | None,
    size: int | None = None,
    box: float | None = None,
) -> str | None:
    """Build the ``/emoji-pad`` proxy URL (``PUBLIC_BASE_URL``/``RENDER_EXTERNAL_URL``).

    Defaults mirror ``EMOJI_PAD_SIZE`` and ``EMOJI_PAD_BOX`` unless overridden.
    """

    if not guild or not tag:
        return None

    emoji = emoji_for_tag(guild, tag)
    if emoji is None:
        return None

    base = _proxy_base_url()
    if not base:
        return None

    query = {
        "u": str(emoji.url),
        "s": str(size or get_emoji_pad_size()),
        "box": str(box or get_emoji_pad_box()),
        "v": str(emoji.id),
    }
    return f"{base}/emoji-pad?{urllib.parse.urlencode(query)}"


async def build_tag_thumbnail(
    guild: discord.Guild | None,
    tag: str | None,
    *,
    size: int = 256,
    box: float = 0.88,
) -> Tuple[discord.File | None, str | None]:
    """Download ``tag`` emoji, pad on a transparent square, and return an attachment.

    Default sizing respects ``TAG_BADGE_PX`` / ``TAG_BADGE_BOX`` when callers leave
    ``size``/``box`` at their defaults.
    """

    if not guild or not tag:
        return None, None

    tag_text = str(tag).strip()
    if not tag_text:
        return None, None

    emoji = emoji_for_tag(guild, tag_text)
    if emoji is None:
        return None, None

    try:
        raw = await emoji.read()
    except Exception:  # pragma: no cover - discord API failures
        log.exception("failed to read emoji payload", extra={"emoji_id": getattr(emoji, "id", None)})
        return None, None

    try:
        image = Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception:  # pragma: no cover - invalid payload
        log.exception("failed to decode emoji image", extra={"emoji_id": getattr(emoji, "id", None)})
        return None, None

    alpha = image.split()[-1]
    bbox = alpha.getbbox()
    if bbox:
        image = image.crop(bbox)

    width, height = image.size
    if width <= 0 or height <= 0:
        return None, None

    canvas_size = max(1, int(size))
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

    min_box, max_box = 0.2, 0.95
    box_ratio = max(min_box, min(max_box, float(box)))
    target = int(canvas_size * box_ratio)
    longest = max(width, height)
    scale = target / float(longest or 1)
    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))
    if new_width != width or new_height != height:
        image = image.resize((new_width, new_height), RESAMPLE_LANCZOS)

    offset = ((canvas_size - new_width) // 2, (canvas_size - new_height) // 2)
    canvas.paste(image, offset, mask=image)

    filename = f"{tag_text.lower() or 'emoji'}-badge.png"
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    buf.seek(0)

    file = discord.File(buf, filename=filename)
    return file, f"attachment://{filename}"


def tag_badge_defaults() -> tuple[int, float]:
    """Return the configured ``TAG_BADGE_PX`` and ``TAG_BADGE_BOX`` values."""

    return get_tag_badge_px(), get_tag_badge_box()


def is_strict_proxy_enabled() -> bool:
    """Return ``True`` when ``STRICT_EMOJI_PROXY`` is active."""

    return get_strict_emoji_proxy()
