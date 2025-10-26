"""Shim module preserving import compatibility for the clan profile cog."""

from __future__ import annotations

from cogs.recruitment_clan_profile import ClanProfileCog, setup

__all__ = ["ClanProfileCog", "setup"]
