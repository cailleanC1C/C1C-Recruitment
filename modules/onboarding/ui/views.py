from __future__ import annotations

import logging
from typing import Optional

import discord

from modules.onboarding import diag

log = logging.getLogger("c1c.onboarding.ui.views")


class NextStepView(discord.ui.View):
    def __init__(self, controller, thread_id: int, index: int, *, timeout: Optional[float] = 300) -> None:
        super().__init__(timeout=timeout)
        self.controller = controller
        self.thread_id = thread_id
        self.index = index
        self.add_item(self.NextButton(self))

    class NextButton(discord.ui.Button):
        def __init__(self, parent: "NextStepView") -> None:
            super().__init__(style=discord.ButtonStyle.primary, label="Open questions")
            self.parent = parent

        async def callback(self, interaction: discord.Interaction) -> None:
            try:
                modal = self.parent.controller.build_modal_stub(self.parent.thread_id)
            except Exception:
                log.warning("failed to build modal stub for next step", exc_info=True)
                if not interaction.response.is_done():
                    try:
                        await interaction.response.send_message(
                            "Couldn\u2019t open the questions just now. Please press the button again.",
                            ephemeral=True,
                        )
                    except Exception:
                        log.warning("failed to notify user about next-step error", exc_info=True)
                return

            try:
                await interaction.response.send_modal(modal)
            except discord.InteractionResponded:
                return

            if diag.is_enabled():
                await diag.log_event(
                    "info",
                    "modal_launch_sent",
                    thread_id=self.parent.thread_id,
                    index=getattr(modal, "step_index", getattr(modal, "_c1c_index", 0)),
                )


__all__ = ["NextStepView"]
