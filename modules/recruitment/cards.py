"""Embed builders for recruitment-related commands and views."""

from __future__ import annotations

import discord

from . import emoji_pipeline


def _set_thumbnail(embed: discord.Embed, guild: discord.Guild | None, tag: str) -> None:
    url = emoji_pipeline.padded_emoji_url(guild, tag)
    if url:
        embed.set_thumbnail(url=url)
        return

    if emoji_pipeline.is_strict_proxy_enabled():
        return

    emoji = emoji_pipeline.emoji_for_tag(guild, tag)
    if emoji:
        embed.set_thumbnail(url=str(emoji.url))


def make_embed_for_row_classic(
    row,
    filters_text: str,
    guild: discord.Guild | None = None,
    *,
    include_crest: bool = True,
) -> discord.Embed:
    """Classic recruiter embed with entry criteria and optional filters footer."""

    clan = (row[1] or "").strip()
    tag = (row[2] or "").strip()
    spots = (row[4] or "").strip()
    inactives = (row[31] if len(row) > 31 else "").strip()
    reserved = (row[28] or "").strip() if len(row) > 28 else ""
    comments = (row[29] or "").strip() if len(row) > 29 else ""
    addl_req = (row[30] or "").strip() if len(row) > 30 else ""

    title = f"{clan} `{tag}`  — Spots: {spots}"
    if inactives:
        title += f" | Inactives: {inactives}"
    if reserved:
        title += f" | Reserved: {reserved}"

    sections = [
        build_entry_criteria_classic(row),
    ]
    if addl_req:
        sections.append(f"**Additional Requirements:** {addl_req}")
    if comments:
        sections.append(f"**Clan Needs/Comments:** {comments}")

    embed = discord.Embed(title=title, description="\n\n".join(sections))

    if include_crest:
        _set_thumbnail(embed, guild, tag)

    embed.set_footer(text=f"Filters used: {filters_text}")
    return embed


def build_entry_criteria_classic(row) -> str:
    """Return the legacy classic entry criteria block."""

    nbsp_pipe = "\u00A0|\u00A0"
    v = (row[21] or "").strip() if len(row) > 21 else ""
    w = (row[22] or "").strip() if len(row) > 22 else ""
    x = (row[23] or "").strip() if len(row) > 23 else ""
    y = (row[24] or "").strip() if len(row) > 24 else ""
    z = (row[25] or "").strip() if len(row) > 25 else ""
    aa = (row[26] or "").strip() if len(row) > 26 else ""
    ab = (row[27] or "").strip() if len(row) > 27 else ""

    lines = ["**Entry Criteria:**"]
    hydra_bits = [part for part in [v and f"{v} keys", x] if part]
    chim_bits = [part for part in [w and f"{w} keys", y] if part]
    if hydra_bits:
        lines.append("Hydra " + nbsp_pipe.join(hydra_bits))
    if chim_bits:
        lines.append("Chimera " + nbsp_pipe.join(chim_bits))
    if z:
        lines.append(f"Clan Boss {z}")
    if aa or ab:
        cvc_bits = []
        if aa:
            cvc_bits.append(f"non PR minimum: {aa}")
        if ab:
            cvc_bits.append(f"PR minimum: {ab}")
        lines.append("CvC " + nbsp_pipe.join(cvc_bits))
    if len(lines) == 1:
        lines.append("—")
    return "\n".join(lines)


def make_embed_for_row_search(
    row,
    filters_text: str,
    guild: discord.Guild | None = None,
) -> discord.Embed:
    """Member-facing entry criteria embed used by clan search flows."""

    name = (row[1] or "").strip()
    tag = (row[2] or "").strip()
    level = (row[3] or "").strip()
    spots = (row[4] or "").strip()

    v = (row[21] or "").strip() if len(row) > 21 else ""
    w = (row[22] or "").strip() if len(row) > 22 else ""
    x = (row[23] or "").strip() if len(row) > 23 else ""
    y = (row[24] or "").strip() if len(row) > 24 else ""
    z = (row[25] or "").strip() if len(row) > 25 else ""
    aa = (row[26] or "").strip() if len(row) > 26 else ""
    ab = (row[27] or "").strip() if len(row) > 27 else ""

    title = f"{name} | {tag} | **Level** {level} | **Spots:** {spots}"

    lines = ["**Entry Criteria:**"]
    if z:
        lines.append(f"Clan Boss: {z}")
    if v or x:
        hydra_bits = []
        if v:
            hydra_bits.append(f"{v} keys")
        if x:
            hydra_bits.append(x)
        lines.append("Hydra: " + " — ".join(hydra_bits))
    if w or y:
        chim_bits = []
        if w:
            chim_bits.append(f"{w} keys")
        if y:
            chim_bits.append(y)
        lines.append("Chimera: " + " — ".join(chim_bits))
    if aa or ab:
        cvc_bits = []
        if aa:
            cvc_bits.append(f"non PR minimum: {aa}")
        if ab:
            cvc_bits.append(f"PR minimum: {ab}")
        lines.append("CvC: " + " | ".join(cvc_bits))
    if len(lines) == 1:
        lines.append("—")

    embed = discord.Embed(title=title, description="\n".join(lines))

    _set_thumbnail(embed, guild, tag)

    if filters_text:
        embed.set_footer(text=f"Filters used: {filters_text}")
    return embed


def make_embed_for_row_lite(
    row,
    filters_text: str,
    guild: discord.Guild | None = None,
) -> discord.Embed:
    """Compact member-facing embed summarising rank, level, and style."""

    name = (row[1] or "").strip()
    tag = (row[2] or "").strip()
    level = (row[3] or "").strip()
    rank_raw = (row[0] or "").strip()
    rank = rank_raw if rank_raw and rank_raw not in {"-", "—"} else ">1k"

    progression = (row[5] or "").strip() if len(row) > 5 else ""
    playstyle = (row[20] or "").strip() if len(row) > 20 else ""
    tail = " | ".join(bit for bit in [progression, playstyle] if bit) or "—"

    title = f"{name} | {tag} | **Level** {level} | **Global Rank** {rank}"
    embed = discord.Embed(title=title, description=tail)

    _set_thumbnail(embed, guild, tag)

    return embed


def make_embed_for_profile(
    row,
    guild: discord.Guild | None = None,
) -> discord.Embed:
    """Full clan profile embed including leadership and activity stats."""

    rank_raw = (row[0] or "").strip()
    rank = rank_raw if rank_raw and rank_raw not in {"-", "—"} else ">1k"

    name = (row[1] or "").strip()
    tag = (row[2] or "").strip()
    level = (row[3] or "").strip()

    lead = (row[6] or "").strip() if len(row) > 6 else ""
    deputies = (row[7] or "").strip() if len(row) > 7 else ""

    cb = (row[12] or "").strip() if len(row) > 12 else ""
    hydra = (row[13] or "").strip() if len(row) > 13 else ""
    chimera = (row[14] or "").strip() if len(row) > 14 else ""

    cvc_tier = (row[8] or "").strip() if len(row) > 8 else ""
    cvc_wins = (row[9] or "").strip() if len(row) > 9 else ""
    siege_tier = (row[10] or "").strip() if len(row) > 10 else ""
    siege_wins = (row[11] or "").strip() if len(row) > 11 else ""

    progression = (row[5] or "").strip() if len(row) > 5 else ""
    playstyle = (row[20] or "").strip() if len(row) > 20 else ""

    title = f"{name} | {tag} | **Level** {level} | **Global Rank** {rank}"

    lines = [
        f"**Clan Lead:** {lead or '—'}",
        f"**Clan Deputies:** {deputies or '—'}",
        "",
        f"**Clan Boss:** {cb or '—'}",
        f"**Hydra:** {hydra or '—'}",
        f"**Chimera:** {chimera or '—'}",
        "",
        f"**CvC**: Tier {cvc_tier or '—'} | Wins {cvc_wins or '—'}",
        f"**Siege:** Tier {siege_tier or '—'} | Wins {siege_wins or '—'}",
        "",
    ]

    footer_tail = " | ".join(bit for bit in [progression, playstyle] if bit)
    if footer_tail:
        lines.append(footer_tail)

    embed = discord.Embed(title=title, description="\n".join(lines))

    _set_thumbnail(embed, guild, tag)
    embed.set_footer(text="React with 💡 for Entry Criteria")
    return embed
