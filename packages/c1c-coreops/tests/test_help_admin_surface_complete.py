import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, Mapping, Sequence

import discord
import pytest
from discord.ext import commands


def _ensure_src_on_path() -> None:
    root = Path(__file__).resolve().parents[3]
    src = root / "packages" / "c1c-coreops" / "src"
    root_str = str(root)
    src_str = str(src)
    if root_str not in __import__("sys").path:
        __import__("sys").path.insert(0, root_str)
    if src_str not in __import__("sys").path:
        __import__("sys").path.insert(0, src_str)


def _resolve_member(target):
    if isinstance(target, commands.Context):
        return getattr(target, "author", None)
    return target


_ensure_src_on_path()

from c1c_coreops.cog import CoreOpsCog
from c1c_coreops.helpers import tier
from modules.ops.permissions_sync import BotPermissionCog
from cogs.recruitment_clan_profile import ClanProfileCog
from cogs.recruitment_member import RecruitmentMember
from cogs.recruitment_recruiter import RecruiterPanelCog
from cogs.recruitment_welcome import WelcomeBridge


class DummyMember:
    def __init__(self, *, is_admin: bool = False, is_staff: bool = False) -> None:
        self.display_name = "Member"
        self.id = 1 if is_admin else 2 if is_staff else 3
        self.roles: list[SimpleNamespace] = []
        self.guild_permissions = SimpleNamespace(administrator=is_admin)
        self._is_admin = is_admin
        self._is_staff = is_staff

    def __str__(self) -> str:  # pragma: no cover - defensive fallback
        return self.display_name


class HelpContext:
    def __init__(self, bot: commands.Bot, author: DummyMember) -> None:
        self.bot = bot
        self.author = author
        self.guild = SimpleNamespace(id=1234)
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
def patch_rbac(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    monkeypatch.setattr("c1c_coreops.rbac.get_admin_role_ids", lambda: set())
    monkeypatch.setattr("c1c_coreops.rbac.get_staff_role_ids", lambda: set())
    monkeypatch.setattr("c1c_coreops.rbac._resolve_member", _resolve_member)
    monkeypatch.setattr(
        "c1c_coreops.rbac._member_has_admin_role",
        lambda member: bool(getattr(member, "_is_admin", False)),
    )
    monkeypatch.setattr(
        "c1c_coreops.rbac._has_administrator_permission",
        lambda member: bool(
            getattr(getattr(member, "guild_permissions", None), "administrator", False)
        ),
    )
    monkeypatch.setattr(
        "c1c_coreops.rbac.is_admin_member",
        lambda target: bool(getattr(_resolve_member(target), "_is_admin", False)),
    )
    monkeypatch.setattr(
        "c1c_coreops.rbac.is_staff_member",
        lambda target: bool(
            getattr(_resolve_member(target), "_is_staff", False)
            or getattr(_resolve_member(target), "_is_admin", False)
        ),
    )
    monkeypatch.setattr(
        "c1c_coreops.rbac.is_recruiter",
        lambda target: bool(getattr(_resolve_member(target), "_is_staff", False)),
    )
    monkeypatch.setattr(
        "c1c_coreops.rbac.is_lead",
        lambda target: bool(getattr(_resolve_member(target), "_is_staff", False)),
    )
    monkeypatch.setattr(
        "c1c_coreops.rbac.ops_gate",
        lambda member: bool(getattr(member, "_is_admin", False) or getattr(member, "_is_staff", False)),
    )
    monkeypatch.setattr(
        "c1c_coreops.rbac.can_view_admin",
        lambda target: bool(getattr(_resolve_member(target), "_is_admin", False)),
    )
    monkeypatch.setattr(
        "c1c_coreops.rbac.can_view_staff",
        lambda target: bool(
            getattr(_resolve_member(target), "_is_staff", False)
            or getattr(_resolve_member(target), "_is_admin", False)
        ),
    )
    monkeypatch.setattr(
        "c1c_coreops.cog.can_view_admin",
        lambda target: bool(getattr(_resolve_member(target), "_is_admin", False)),
    )
    monkeypatch.setattr(
        "c1c_coreops.cog.can_view_staff",
        lambda target: bool(
            getattr(_resolve_member(target), "_is_staff", False)
            or getattr(_resolve_member(target), "_is_admin", False)
        ),
    )
    monkeypatch.setattr("c1c_coreops.rbac.discord.Member", DummyMember)
    monkeypatch.setattr("c1c_coreops.cog.discord.Member", DummyMember)
    yield


async def _gather_help_embeds(
    monkeypatch: pytest.MonkeyPatch,
    member: DummyMember,
    *,
    show_empty: bool = False,
) -> list[discord.Embed]:
    if show_empty:
        monkeypatch.setenv("SHOW_EMPTY_SECTIONS", "1")
    else:
        monkeypatch.delenv("SHOW_EMPTY_SECTIONS", raising=False)

    bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())

    @tier("user")
    @bot.command(name="placeholder")
    async def _placeholder(_: commands.Context) -> None:  # pragma: no cover - helper
        return None

    await bot.add_cog(CoreOpsCog(bot))
    await bot.add_cog(BotPermissionCog(bot))
    await bot.add_cog(RecruiterPanelCog(bot))
    await bot.add_cog(WelcomeBridge(bot))
    await bot.add_cog(RecruitmentMember(bot))
    await bot.add_cog(ClanProfileCog(bot))

    try:
        cog = bot.get_cog("CoreOpsCog")
        assert cog is not None
        ctx = HelpContext(bot, author=member)
        await cog.render_help(ctx)
        assert len(ctx._replies) == 4, "Help should return four embeds"
        return ctx._replies
    finally:
        await bot.close()


def _fields(embed: discord.Embed) -> Mapping[str, str]:
    mapping: dict[str, str] = {}
    for field in getattr(embed, "fields", []):
        mapping[getattr(field, "name", "")] = getattr(field, "value", "")
    return mapping


def test_help_admin_embed_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        embeds = await _gather_help_embeds(monkeypatch, DummyMember(is_admin=True, is_staff=True))
        titles = {embed.title: embed for embed in embeds}
        admin_embed = titles["Admin / Operational"]
        staff_embed = titles["Staff"]
        user_embed = titles["User"]

        admin_text = " \n ".join(_fields(admin_embed).values())
        staff_text = " \n ".join(_fields(staff_embed).values())
        user_text = " \n ".join(_fields(user_embed).values())

        assert "`!welcome-refresh`" in admin_text
        assert "`!perm bot list`" in admin_text
        assert "`@Bot help`" not in admin_text
        assert "`@Bot ping`" not in admin_text
        assert "`!clanmatch`" not in admin_text

        assert "`!clanmatch`" in staff_text
        assert "`!welcome-refresh`" not in staff_text
        assert "`@Bot help`" not in staff_text

        assert "`@Bot help`" in user_text
        assert "`@Bot ping`" in user_text
        assert "`!welcome-refresh`" not in user_text

    asyncio.run(runner())


def test_help_staff_embed_excludes_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        embeds = await _gather_help_embeds(monkeypatch, DummyMember(is_staff=True))
        titles = {embed.title: embed for embed in embeds}
        admin_embed = titles["Admin / Operational"]
        staff_embed = titles["Staff"]
        user_embed = titles["User"]

        admin_text = " \n ".join(_fields(admin_embed).values())
        staff_text = " \n ".join(_fields(staff_embed).values())
        user_text = " \n ".join(_fields(user_embed).values())

        assert "`!welcome-refresh`" not in admin_text
        assert "`!perm bot list`" not in admin_text
        assert "`!clanmatch`" in staff_text
        assert "`@Bot help`" in user_text
        assert "`!welcome-refresh`" not in staff_text

    asyncio.run(runner())


def test_help_user_embed_mentions_only(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        embeds = await _gather_help_embeds(monkeypatch, DummyMember())
        titles = {embed.title: embed for embed in embeds}
        admin_embed = titles["Admin / Operational"]
        staff_embed = titles["Staff"]
        user_embed = titles["User"]

        admin_text = " \n ".join(_fields(admin_embed).values())
        staff_text = " \n ".join(_fields(staff_embed).values())
        user_text = " \n ".join(_fields(user_embed).values())

        assert "@Bot help" not in admin_text
        assert "@Bot help" not in staff_text
        assert "@Bot help" in user_text
        assert "@Bot ping" in user_text

    asyncio.run(runner())


def test_help_empty_sections_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        embeds = await _gather_help_embeds(
            monkeypatch, DummyMember(), show_empty=True
        )
        titles = {embed.title: embed for embed in embeds}
        user_embed = titles["User"]
        fields = _fields(user_embed)
        assert "Milestones" in fields
        assert fields["Milestones"] == "Coming soon"

    asyncio.run(runner())
