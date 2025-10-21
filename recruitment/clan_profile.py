"""Prefix command for clan profile cards with crest thumbnails."""

from __future__ import annotations

import discord
from discord.ext import commands

from recruitment import cards, emoji_pipeline
from recruitment.views import SearchResultFlipView
from shared.coreops.helpers.tiers import tier
from sheets import recruitment as recruitment_sheets

_VALID_TAG_CHARS: frozenset[str] = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


def _normalize_tag(raw: str | None) -> str:
    if raw is None:
        return ""
    text = "".join(ch for ch in str(raw).upper() if ch in _VALID_TAG_CHARS)
    return text.strip()


def _error_embed(tag: str) -> discord.Embed:
    description = f"Unknown clan tag `{tag}`."
    return discord.Embed(description=description, color=discord.Color.red())


class ClanProfileCog(commands.Cog):
    """Registers the `!clan <tag>` profile card command."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @tier("user")
    @commands.command(
        name="clan",
        help="Show a clan’s profile card by tag (with crest).",
        usage="clan <tag>",
    )
    async def clan(self, ctx: commands.Context, tag: str) -> None:
        """Render a clan profile card with crest and entry criteria flip."""

        normalized = _normalize_tag(tag)
        if not (2 <= len(normalized) <= 5):
            await ctx.reply(embed=_error_embed(tag or "?"), mention_author=False)
            return

        row = recruitment_sheets.get_clan_by_tag(normalized)
        if row is None:
            await ctx.reply(embed=_error_embed(normalized), mention_author=False)
            return

        row_tag = _normalize_tag(row[2] if len(row) > 2 else normalized) or normalized

        badge_size, badge_box = emoji_pipeline.tag_badge_defaults()
        crest_file: discord.File | None = None
        crest_url: str | None = None
        if ctx.guild:
            file, url = await emoji_pipeline.build_tag_thumbnail(
                ctx.guild,
                row_tag,
                size=badge_size,
                box=badge_box,
            )
            if file and url:
                crest_file = file
                crest_url = url
            else:
                proxy_url = emoji_pipeline.padded_emoji_url(ctx.guild, row_tag)
                if proxy_url:
                    crest_url = proxy_url
                elif not emoji_pipeline.is_strict_proxy_enabled():
                    emoji = emoji_pipeline.emoji_for_tag(ctx.guild, row_tag)
                    if emoji:
                        crest_url = str(emoji.url)

        def _profile_embed() -> discord.Embed:
            embed = cards.make_embed_for_profile(row, guild=ctx.guild)
            if crest_url:
                embed.set_thumbnail(url=crest_url)
            embed.set_footer(text="Use the buttons below to view entry criteria.")
            return embed

        def _entry_embed() -> discord.Embed:
            embed = cards.make_embed_for_row_lite(row, filters_text="", guild=ctx.guild)
            embed.set_thumbnail(url=discord.Embed.Empty)
            embed.set_footer(text="Use the buttons below to return to the profile.")
            return embed

        view = SearchResultFlipView(
            author_id=ctx.author.id if ctx.author else 0,
            row=row,
            filters_text="",
            guild=ctx.guild,
            default_mode="profile",
            embed_builders={
                "profile": _profile_embed,
                "entry": _entry_embed,
            },
            not_owner_message=f"⚠️ Not your card. Run **!clan {row_tag}** to open your own.",
        )

        profile_embed = _profile_embed()
        files: list[discord.File] = []
        if crest_file is not None:
            files.append(crest_file)

        target = await _resolve_destination(ctx)

        if files:
            sent = await target.send(embed=profile_embed, view=view, files=files)
        else:
            sent = await target.send(embed=profile_embed, view=view)
        view.message = sent

        if target is not ctx.channel:
            try:
                await ctx.reply(
                    f"{ctx.author.mention} posted `{row_tag}` in {target.mention}: {sent.jump_url}",
                    mention_author=False,
                    allowed_mentions=discord.AllowedMentions(users=[ctx.author] if ctx.author else []),
                    suppress_embeds=True,
                )
            except Exception:  # pragma: no cover - pointer best effort
                pass


async def _resolve_destination(
    ctx: commands.Context,
) -> discord.abc.MessageableChannel:
    """Return the channel/thread where the clan profile should be sent."""

    thread = None
    try:
        from shared import config as _cfg

        mode = getattr(_cfg, "get_panel_thread_mode", lambda: "channel")()
        fixed_id = getattr(_cfg, "get_panel_fixed_thread_id", lambda: None)()
        if (
            str(mode).lower() == "fixed"
            and fixed_id
            and ctx.guild
        ):
            thread = ctx.guild.get_thread(int(fixed_id))
            if thread is None and ctx.bot:
                try:
                    thread = await ctx.bot.fetch_channel(int(fixed_id))
                except Exception:
                    thread = None
            if isinstance(thread, discord.Thread) and thread.archived:
                try:
                    await thread.edit(archived=False)
                except Exception:
                    pass
    except Exception:
        thread = None

    if thread and hasattr(thread, "send"):
        return thread
    return ctx.channel  # type: ignore[return-value]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ClanProfileCog(bot))
