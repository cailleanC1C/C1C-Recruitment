"""Theme helpers for embeds and branded surfaces."""

from __future__ import annotations

import discord

from shared.config import cfg

__all__ = ["colors", "get_icon"]

_DEFAULT_ICONS = {
    "crest_or_blue_flame": "🔥",
}


class _ThemeColors:
    __slots__ = ()

    @staticmethod
    def _resolve(name: str, default: int) -> discord.Colour:
        key = f"COLOR_{name}".upper()
        raw = cfg.get(key)
        if isinstance(raw, int):
            try:
                return discord.Colour(int(raw))
            except Exception:  # pragma: no cover - defensive fallback
                return discord.Colour(default)
        if isinstance(raw, str):
            text = raw.strip()
            if text.startswith("#"):
                text = text[1:]
            if text.lower().startswith("0x"):
                text = text[2:]
            try:
                return discord.Colour(int(text, 16))
            except Exception:  # pragma: no cover - defensive fallback
                return discord.Colour(default)
        return discord.Colour(default)

    @property
    def c1c_blue(self) -> discord.Colour:
        return self._resolve("c1c_blue", 0x1F8BFF)

    @property
    def admin(self) -> discord.Colour:
        return self._resolve("admin", 0xF200E5)


colors = _ThemeColors()


def get_icon(name: str) -> str:
    """Return the icon token for ``name`` using config overrides when present."""

    if not name:
        return ""
    normalized = name.strip()
    if not normalized:
        return ""
    config_keys = (
        f"ICON_{normalized}".upper(),
        f"{normalized}_ICON".upper(),
    )
    for key in config_keys:
        value = cfg.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _DEFAULT_ICONS.get(normalized, "")
