from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
import discord
from discord.ext import commands

from c1c_coreops.cog import CoreOpsCog
from c1c_coreops.prefix import detect_admin_bang_command
from c1c_coreops import rbac


def test_tagged_only_model(monkeypatch):
    monkeypatch.setenv("BOT_TAG", "rec")
    monkeypatch.setenv("COREOPS_ENABLE_TAGGED_ALIASES", "1")
    monkeypatch.setenv("COREOPS_ENABLE_GENERIC_ALIASES", "0")
    monkeypatch.delenv("COREOPS_ADMIN_BANG_ALLOWLIST", raising=False)

    intents = discord.Intents.none()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    async def runner() -> None:
        try:
            cog = CoreOpsCog(bot)
            await bot.add_cog(cog)

            # Tagged command group stays available.
            assert bot.get_command("rec env") is not None
            # Generic aliases remain unregistered when disabled.
            assert bot.get_command("env") is None

            non_admin = SimpleNamespace()
            message = SimpleNamespace(content="!env", author=non_admin)
            assert (
                detect_admin_bang_command(
                    message,
                    commands=cog._admin_bang_allowlist,
                    is_admin=lambda _: False,
                )
                is None
            )

            admin = SimpleNamespace()
            bang_target = detect_admin_bang_command(
                SimpleNamespace(content="!env", author=admin),
                commands=cog._admin_bang_allowlist,
                is_admin=lambda _: True,
            )
            assert bang_target == "env"

            # Fallback ensures admins route to the tagged command even when generics are removed.
            fallback = bot.get_command(f"rec {bang_target}")
            assert fallback is not None
        finally:
            await bot.close()

    asyncio.run(runner())


def test_generic_alias_toggle(monkeypatch):
    monkeypatch.setenv("BOT_TAG", "ach")
    monkeypatch.setenv("COREOPS_ENABLE_TAGGED_ALIASES", "1")
    monkeypatch.setenv("COREOPS_ENABLE_GENERIC_ALIASES", "1")

    intents = discord.Intents.none()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    async def runner() -> None:
        try:
            cog = CoreOpsCog(bot)
            await bot.add_cog(cog)

            # Tagged alias registers for the configured tag.
            assert "ach" in tuple(cog.rec.aliases)
            # Generic aliases are kept when enabled.
            assert bot.get_command("env") is not None
            assert bot.get_command("refresh all") is not None
        finally:
            await bot.close()

    asyncio.run(runner())


def test_allowlist_enforced(monkeypatch):
    monkeypatch.setenv("BOT_TAG", "rec")
    monkeypatch.setenv("COREOPS_ENABLE_TAGGED_ALIASES", "1")
    monkeypatch.setenv("COREOPS_ENABLE_GENERIC_ALIASES", "0")
    monkeypatch.setenv("COREOPS_ADMIN_BANG_ALLOWLIST", "env,refresh all")

    intents = discord.Intents.none()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    async def runner() -> None:
        try:
            cog = CoreOpsCog(bot)
            await bot.add_cog(cog)

            admin = SimpleNamespace()
            allowed = detect_admin_bang_command(
                SimpleNamespace(content="!refresh all", author=admin),
                commands=cog._admin_bang_allowlist,
                is_admin=lambda _: True,
            )
            assert allowed == "refresh all"

            blocked = detect_admin_bang_command(
                SimpleNamespace(content="!foo", author=admin),
                commands=cog._admin_bang_allowlist,
                is_admin=lambda _: True,
            )
            assert blocked is None
        finally:
            await bot.close()

    asyncio.run(runner())


def test_rbac_checks_respected(monkeypatch):
    monkeypatch.setenv("BOT_TAG", "rec")
    monkeypatch.setenv("COREOPS_ENABLE_TAGGED_ALIASES", "1")
    monkeypatch.setenv("COREOPS_ENABLE_GENERIC_ALIASES", "0")

    intents = discord.Intents.none()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    class FakePermissions:
        def __init__(self, administrator: bool = False) -> None:
            self.administrator = administrator

    class FakeMember:
        def __init__(self, administrator: bool = False) -> None:
            self.roles = []
            self.guild_permissions = FakePermissions(administrator)

    class FakeContext(SimpleNamespace):
        _coreops_suppress_denials = True

    monkeypatch.setattr(rbac, "_member_has_admin_role", lambda member: False)
    monkeypatch.setattr(
        rbac,
        "_has_administrator_permission",
        lambda member: member.guild_permissions.administrator,
    )
    monkeypatch.setattr(rbac.discord, "Member", FakeMember)

    async def runner() -> None:
        try:
            cog = CoreOpsCog(bot)
            await bot.add_cog(cog)

            reload_command = bot.get_command("rec reload")
            assert reload_command is not None

            check = rbac.admin_only().predicate

            with pytest.raises(commands.CheckFailure):
                await check(FakeContext(guild=object(), author=FakeMember(administrator=False)))

            assert await check(
                FakeContext(guild=object(), author=FakeMember(administrator=True))
            )
        finally:
            await bot.close()

    asyncio.run(runner())
