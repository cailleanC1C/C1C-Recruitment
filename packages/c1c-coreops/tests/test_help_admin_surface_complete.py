from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, Mapping

import discord
import pytest
from discord.ext import commands

import sys


def _ensure_src_on_path() -> None:
    root = Path(__file__).resolve().parents[3]
    src = root / "packages" / "c1c-coreops" / "src"
    root_str = str(root)
    src_str = str(src)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)


_ensure_src_on_path()

from c1c_coreops.cog import CoreOpsCog
from modules.coreops.helpers import tier


class DummyMember:
    def __init__(self) -> None:
        self.display_name = "Admin"
        self.id = 1
        self.roles: list[SimpleNamespace] = []
        self.guild_permissions = SimpleNamespace(administrator=True)

    def __str__(self) -> str:  # pragma: no cover - defensive fallback
        return self.display_name


class HelpContext:
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.author = DummyMember()
        self.guild = object()
        self._coreops_suppress_denials = True
        self._replies: list[discord.Embed] = []
        self.command = None

    async def reply(self, *args: object, embed: discord.Embed | None = None, **_: object) -> None:
        if embed is not None:
            self._replies.append(embed)


@pytest.fixture(autouse=True)
def patch_coreops_view(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    monkeypatch.setattr("c1c_coreops.cog.can_view_admin", lambda *_: True)
    monkeypatch.setattr("c1c_coreops.cog.can_view_staff", lambda *_: True)
    monkeypatch.setattr("c1c_coreops.rbac.discord.Member", DummyMember)
    monkeypatch.setattr("c1c_coreops.cog.discord.Member", DummyMember)
    yield


def _extract_fields(embed: discord.Embed) -> Mapping[str, str]:
    mapping: dict[str, str] = {}
    for field in getattr(embed, "fields", []):
        name = getattr(field, "name", "")
        value = getattr(field, "value", "")
        mapping[name.strip().lower()] = value
    return mapping


def test_admin_help_lists_bare_and_tagged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TAG", "rec")
    monkeypatch.setenv("COREOPS_ENABLE_TAGGED_ALIASES", "1")
    monkeypatch.setenv("COREOPS_ENABLE_GENERIC_ALIASES", "1")

    async def runner() -> None:
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        
        @tier("admin")
        @bot.command(name="ping", hidden=True)
        async def ping_command(ctx: commands.Context) -> None:  # pragma: no cover - test stub
            return None

        await bot.add_cog(CoreOpsCog(bot))

        try:
            cog = bot.get_cog("CoreOpsCog")
            assert cog is not None
            ctx = HelpContext(bot)
            await cog.render_help(ctx)
            assert ctx._replies, "Help did not reply with an embed"
            fields = _extract_fields(ctx._replies[0])
            admin_block = fields.get("admin", "")
            staff_block = fields.get("recruiter/staff", "")
            user_block = fields.get("user", "")
            combined = "\n".join([admin_block, staff_block, user_block])

            bare_expected = [
                "!checksheet",
                "!config",
                "!digest",
                "!env",
                "!health",
                "!ping",
                "!refresh",
                "!refresh all",
                "!reload",
            ]
            tagged_expected = [
                "!rec checksheet",
                "!rec config",
                "!rec digest",
                "!rec env",
                "!rec health",
                "!rec ping",
                "!rec refresh",
                "!rec refresh all",
                "!rec reload",
            ]

            for entry in bare_expected:
                if entry == "!refresh all":
                    assert (
                        entry in admin_block
                        or f"!rec {entry[1:]}" in admin_block
                    ), f"Expected {entry} or its tagged variant in admin help"
                    continue
                assert entry in admin_block

            for entry in tagged_expected:
                assert (
                    entry in combined
                ), f"Tagged command {entry} missing from help overview"
        finally:
            await bot.close()

    asyncio.run(runner())


def test_admin_help_without_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOT_TAG", raising=False)
    monkeypatch.setenv("COREOPS_ENABLE_TAGGED_ALIASES", "0")
    monkeypatch.setenv("COREOPS_ENABLE_GENERIC_ALIASES", "1")

    async def runner() -> None:
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        
        @tier("admin")
        @bot.command(name="ping", hidden=True)
        async def ping_command(ctx: commands.Context) -> None:  # pragma: no cover - test stub
            return None

        await bot.add_cog(CoreOpsCog(bot))

        try:
            cog = bot.get_cog("CoreOpsCog")
            assert cog is not None
            ctx = HelpContext(bot)
            await cog.render_help(ctx)
            assert ctx._replies
            fields = _extract_fields(ctx._replies[0])
            admin_block = fields.get("admin", "")
            for entry in [
                "!checksheet",
                "!config",
                "!digest",
                "!env",
                "!health",
                "!ping",
                "!refresh",
                "!refresh all",
                "!reload",
            ]:
                if entry == "!refresh all":
                    assert (
                        entry in admin_block
                        or f"!rec {entry[1:]}" in admin_block
                    )
                    continue
                assert entry in admin_block
        finally:
            await bot.close()

    asyncio.run(runner())
