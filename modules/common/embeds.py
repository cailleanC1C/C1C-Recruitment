from __future__ import annotations

"""Shared helpers for Discord embeds."""

from typing import Literal

import discord


EmbedCategory = Literal["admin", "recruitment", "community"]

_COLOURS: dict[EmbedCategory, discord.Colour] = {
    "admin": discord.Colour(0xF200E5),
    "recruitment": discord.Colour(0x1B8009),
    "community": discord.Colour(0x3498DB),
}


def get_embed_colour(category: EmbedCategory) -> discord.Colour:
    """Return the embed colour for the given category."""

    return _COLOURS.get(category, discord.Colour.default())


__all__ = ["EmbedCategory", "get_embed_colour"]
