"""Builders for recruitment welcome and promo summary embeds."""

from __future__ import annotations

from typing import Any, Mapping

import discord

from modules.recruitment.summary_map import SUMMARY_FRAME, SUMMARY_LAYOUTS, SUMMARY_SECTIONS
from shared.formatters.summary import abbr_number, cvc_priority, inline_merge
from shared import theme

__all__ = ["build_promo_summary_embed", "build_welcome_summary_embed"]

_DEFAULT_SECTION_TITLES = {
    "bossing": "🧩 Progress & Bossing",
    "war": "⚔️ War Modes",
    "notes": "🧭 Notes",
}

_HIDE_TOKENS = {"", "0", "no", "none", "dunno"}


def build_promo_summary_embed(
    flow: str,
    answers: Mapping[str, Any],
    visibility: Mapping[str, Mapping[str, str]] | None,
    *,
    author: discord.abc.User | discord.Member | None = None,
) -> discord.Embed:
    """Return the embed summarising promo questionnaire answers for ``flow``."""

    return _build_summary_embed(flow, answers, visibility, author=author)


def build_welcome_summary_embed(
    answers: Mapping[str, Any],
    visibility: Mapping[str, Mapping[str, str]] | None,
    *,
    author: discord.abc.User | discord.Member | None = None,
) -> discord.Embed:
    """Return the embed summarising the welcome questionnaire answers."""

    return _build_summary_embed("welcome", answers, visibility, author=author)


def _build_summary_embed(
    flow: str,
    answers: Mapping[str, Any],
    visibility: Mapping[str, Mapping[str, str]] | None,
    *,
    author: discord.abc.User | discord.Member | None = None,
) -> discord.Embed:
    layout = _layout_for(flow)
    frame = layout.get("frame", SUMMARY_FRAME)
    sections = layout.get("sections", SUMMARY_SECTIONS)
    section_titles = {**_DEFAULT_SECTION_TITLES, **layout.get("section_titles", {})}

    icon_token = theme.get_icon(frame.get("icon", ""))
    title = frame.get("title", "C1C • Recruitment Summary")
    if icon_token:
        title = f"{icon_token} {title}"

    colour_name = frame.get("color", "c1c_blue")
    colour = getattr(theme.colors, colour_name, theme.colors.c1c_blue)

    description = frame.get(
        "description", "Keep this thread open until a recruiter confirms placement."
    )

    embed = discord.Embed(title=title, description=description, colour=colour)
    footer = frame.get("footer")
    if footer:
        embed.set_footer(text=footer)

    if author is not None:
        display_name = getattr(author, "display_name", None) or getattr(author, "name", "")
        avatar = getattr(author, "display_avatar", None)
        if avatar:
            embed.set_author(name=display_name or "", icon_url=avatar.url)
        elif display_name:
            embed.set_author(name=display_name)

    answers_map = dict(answers)
    visible_gids = _resolve_visible_gids(answers_map, visibility)

    identity_lines: list[str] = []

    for section in sections:
        section_lines = _render_section(section, answers_map, visible_gids)
        if not section_lines:
            continue
        name = section.get("name", "")
        if name == "identity":
            identity_lines.extend(section_lines)
            continue
        header = section.get("title") or section_titles.get(name, name.title() if name else "")
        embed.add_field(name=header or "Summary", value="\n".join(section_lines), inline=False)

    if identity_lines:
        embed.description = "\n\n".join([description, "\n".join(identity_lines)])

    return embed


def _resolve_visible_gids(
    answers: Mapping[str, Any],
    visibility: Mapping[str, Mapping[str, str]] | None,
) -> set[str]:
    if not visibility:
        return {str(key) for key in answers.keys()}
    visible: set[str] = set()
    for qid, entry in visibility.items():
        state = str(entry.get("state", "show")).strip().lower()
        if state != "skip":
            visible.add(qid)
    for qid in answers.keys():
        if qid not in visibility:
            visible.add(qid)
    return visible


def _render_section(
    section: Mapping[str, Any],
    answers: Mapping[str, Any],
    visible_gids: set[str],
) -> list[str]:
    fields = section.get("fields", [])
    index = {field.get("gid"): field for field in fields if field.get("gid")}
    inline_targets = {
        field.get("inline_with")
        for field in fields
        if field.get("inline_with")
    }
    consumed: set[str] = set()
    lines: list[str] = []
    for field in fields:
        gid = field.get("gid")
        if not gid or gid in consumed:
            continue
        if gid in inline_targets and gid not in consumed:
            # Inline partner will handle rendering this field.
            continue
        inline_partner = field.get("inline_with")
        if inline_partner:
            partner_cfg = index.get(inline_partner, {"gid": inline_partner})
            primary_value = _resolved_value(field, answers, visible_gids)
            partner_value = _resolved_value(partner_cfg, answers, visible_gids)
            consumed.add(gid)
            consumed.add(inline_partner)
            if not primary_value and not partner_value:
                continue
            line = _combine_inline(field, primary_value, partner_cfg, partner_value)
            if line:
                lines.append(line)
            continue
        value = _resolved_value(field, answers, visible_gids)
        consumed.add(gid)
        if not value:
            continue
        label = field.get("label")
        lines.append(_labelled(label, value))
    return lines


def _combine_inline(
    primary: Mapping[str, Any],
    primary_value: str,
    partner: Mapping[str, Any],
    partner_value: str,
) -> str:
    if primary_value and partner_value:
        partner_first = not partner.get("inline", False)
        if partner_first:
            return inline_merge(
                partner.get("label"),
                partner_value,
                primary.get("label"),
                primary_value,
            )
        return inline_merge(
            primary.get("label"),
            primary_value,
            partner.get("label"),
            partner_value,
        )
    if primary_value:
        return _labelled(primary.get("label"), primary_value)
    if partner_value:
        return _labelled(partner.get("label"), partner_value)
    return ""


def _resolved_value(
    field: Mapping[str, Any],
    answers: Mapping[str, Any],
    visible_gids: set[str],
) -> str:
    gid = field.get("gid")
    if not gid:
        return ""
    if visible_gids and gid not in visible_gids:
        return ""
    raw = answers.get(gid)
    formatted = _format_value(field, raw)
    required_gid = field.get("requires")
    if required_gid:
        required_value = _format_value({}, answers.get(required_gid))
        if should_hide_value(required_value):
            return ""
    hide_tokens = {
        str(token).strip().lower()
        for token in field.get("hide_if_values", [])
        if isinstance(token, str)
    }
    if formatted and hide_tokens and formatted.strip().lower() in hide_tokens:
        return ""
    force_show = bool(field.get("force_show"))
    if should_hide_value(formatted, force_show=force_show):
        if force_show:
            return "—"
        return ""
    if force_show and not formatted:
        return "—"
    return formatted


def _labelled(label: str | None, value: str) -> str:
    if not label:
        return value
    return f"**{label}:** {value}"


def _format_value(field: Mapping[str, Any], value: Any) -> str:
    base = _stringify(value)
    fmt = field.get("fmt") if isinstance(field, Mapping) else None
    formatted = base
    if fmt == "abbr_number":
        formatted = abbr_number(value)
        if not formatted:
            formatted = base
    elif fmt == "cvc_priority":
        formatted = cvc_priority(value)
        if not formatted:
            formatted = base
    truncate = field.get("truncate") if isinstance(field, Mapping) else None
    if truncate and formatted:
        formatted = truncate_text(formatted, int(truncate))
    return formatted


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple, set)):
        parts = [_stringify(item) for item in value]
        return ", ".join(filter(None, parts))
    if isinstance(value, dict):
        if "values" in value and isinstance(value["values"], list):
            parts = [_stringify(item) for item in value["values"]]
            joined = ", ".join(filter(None, parts))
            if joined:
                return joined
        label = value.get("label") or value.get("value")
        if isinstance(label, str):
            return label.strip()
        if label is not None:
            return str(label).strip()
        return ""
    text = str(value).strip()
    return text


def should_hide_value(value: Any, *, force_show: bool = False) -> bool:
    if force_show:
        return False
    if value is None:
        return True
    token = str(value).strip().lower()
    return token in _HIDE_TOKENS


def truncate_text(value: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(value) <= limit:
        return value
    trimmed = value[: max(limit - 1, 0)].rstrip()
    return f"{trimmed}…"


def _layout_for(flow: str) -> Mapping[str, Any]:
    if flow in SUMMARY_LAYOUTS:
        return SUMMARY_LAYOUTS[flow]
    return SUMMARY_LAYOUTS.get(
        "welcome", {"frame": SUMMARY_FRAME, "sections": SUMMARY_SECTIONS}
    )
