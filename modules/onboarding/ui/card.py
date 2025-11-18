"""Rolling onboarding card utilities."""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import discord


class RollingCard:
    """Maintain and update a single onboarding message within a thread."""

    def __init__(self, channel: discord.abc.Messageable) -> None:
        self.channel = channel
        self.message: Optional[discord.Message] = None

    async def ensure(self) -> discord.Message:
        if self.message is None:
            self.message = await self.channel.send("Starting onboarding…")
        return self.message

    def _badge(self, badge_kind: str | None) -> str | None:
        if badge_kind == "required":
            return "Input is required"
        if badge_kind == "optional":
            return "Input is optional"
        return None

    async def render_question(
        self,
        *,
        index: int,
        total: int,
        title: str,
        help_text: str,
        badge_kind: str | None,
        status: Tuple[str, str] | None,
        view: Optional[discord.ui.View],
        answer_preview: str | None = None,
        note: str | None = None,
        helper_line: str | None = None,
    ) -> None:
        message = await self.ensure()
        progress_total = max(total, 1)
        header = f"**Onboarding • {index}/{progress_total}"
        badge = self._badge(badge_kind)
        if badge:
            header = f"{header} • {badge}"
        header = f"{header}**"

        lines: List[str] = [header, "", f"### {title}"]

        if help_text:
            lines.append(f"_{help_text}_")

        if helper_line:
            lines.append("")
            lines.append(helper_line)

        if answer_preview:
            lines.append("")
            lines.append(f"**Current answer:** {answer_preview}")

        if note:
            lines.append("")
            lines.append(note)

        if status:
            icon, text = status
            if text:
                lines.append("")
                lines.append(f"{icon} {text}")

        body = "\n".join(lines).strip()
        await message.edit(content=body, view=view)

    async def render_summary(
        self,
        *,
        items: Sequence[Tuple[str, str]],
    ) -> None:
        message = await self.ensure()
        lines: List[str] = ["**Onboarding — Summary**"]
        if items:
            for title, value in items:
                lines.append("")
                lines.append(f"**{title}**")
                lines.append(f"> {value or '—'}")
        else:
            lines.append("")
            lines.append("No answers were captured.")
        await message.edit(content="\n".join(lines), view=None)
