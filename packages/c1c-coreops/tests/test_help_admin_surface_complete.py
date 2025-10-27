from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, Mapping, Sequence

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
from c1c_coreops.helpers import tier
from modules.ops.permissions_sync import BotPermissionCog


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

    async def reply(
        self,
        *args: object,
        embed: discord.Embed | None = None,
        embeds: Sequence[discord.Embed] | None = None,
        **_: object,
    ) -> None:
        if embed is not None:
            self._replies.append(embed)
        if embeds:
            self._replies.extend(embeds)


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
    monkeypatch.setenv("COREOPS_ENABLE_GENERIC_ALIASES", "0")

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
            assert ctx._replies, "Help did not reply with embeds"
            assert len(ctx._replies) == 4

            overview = ctx._replies[0]
            assert overview.title == "C1C-Recruitment — help"

            embeds_by_title = {embed.title: embed for embed in ctx._replies[1:]}
            admin_embed = embeds_by_title.get("Admin / Operational")
            staff_embed = embeds_by_title.get("Staff")
            user_embed = embeds_by_title.get("User")
            assert admin_embed and staff_embed and user_embed

            admin_fields = _extract_fields(admin_embed)
            staff_fields = _extract_fields(staff_embed)
            user_fields = _extract_fields(user_embed)

            admin_text = " \n ".join(admin_fields.values())
            staff_text = " \n ".join(staff_fields.values())
            user_text = " \n ".join(user_fields.values())

            for expected in (
                "`!rec env`",
                "`!rec health`",
                "`!perm bot list`",
                "`!perm bot sync`",
                "`!welcome-refresh`",
                "`!rec reload`",
            ):
                assert (
                    expected in admin_text
                ), f"Expected {expected} in admin embed"

            for expected in (
                "`!rec checksheet`",
                "`!rec config`",
                "`!rec digest`",
                "`!rec refresh`",
                "`!rec refresh all`",
                "`!clanmatch`",
                "`!welcome`",
            ):
                assert (
                    expected in staff_text
                ), f"Expected {expected} in staff embed"

            for expected in (
                "`@Bot help`",
                "`@Bot ping`",
                "`!clan`",
                "`!clansearch`",
            ):
                assert (
                    expected in user_text
                ), f"Expected {expected} in user embed"
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
            admin_embed = next(
                (embed for embed in ctx._replies if embed.title == "Admin / Operational"),
                None,
            )
            assert admin_embed is not None
            admin_text = " \n ".join(_extract_fields(admin_embed).values())
            for entry in (
                "`!rec env`",
                "`!rec health`",
                "`!rec refresh`",
                "`!rec refresh all`",
                "`!rec reload`",
            ):
                assert entry in admin_text
        finally:
            await bot.close()

    asyncio.run(runner())


def test_admin_help_includes_perm_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TAG", "rec")
    monkeypatch.setenv("COREOPS_ENABLE_TAGGED_ALIASES", "1")
    monkeypatch.setenv("COREOPS_ENABLE_GENERIC_ALIASES", "0")

    async def runner() -> None:
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())

        await bot.add_cog(CoreOpsCog(bot))
        await bot.add_cog(BotPermissionCog(bot))

        try:
            cog = bot.get_cog("CoreOpsCog")
            assert cog is not None
            ctx = HelpContext(bot)
            await cog.render_help(ctx)
            assert ctx._replies, "Help did not reply with embeds"
            admin_embed = next(
                (embed for embed in ctx._replies if embed.title == "Admin / Operational"),
                None,
            )
            assert admin_embed is not None
            admin_text = " \n ".join(_extract_fields(admin_embed).values())

            for entry in (
                "`!perm bot list`",
                "`!perm bot allow`",
                "`!perm bot deny`",
                "`!perm bot remove`",
                "`!perm bot sync`",
            ):
                assert entry in admin_text, f"Expected {entry} in admin help output"
        finally:
            await bot.close()

    asyncio.run(runner())
