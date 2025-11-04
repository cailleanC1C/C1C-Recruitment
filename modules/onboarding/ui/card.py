"""Rolling onboarding card utilities."""
from __future__ import annotations

from typing import List, Optional

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

    async def render(
        self,
        index: int,
        total: int,
        label: str,
        help_text: str,
        summary: List[str],
        view: Optional[discord.ui.View],
    ) -> None:
        message = await self.ensure()
        body = f"**Onboarding • {index}/{total}**\n{label}"
        if help_text:
            body += f"\n*{help_text}*"
        if summary:
            body += "\n\n**So far**\n" + "\n".join(summary)
        await message.edit(content=body, view=view)

    async def hint(self, text: str) -> None:
        if self.message is None:
            return
        await self.message.edit(content=f"{self.message.content}\n\n❌ *{text}*")
