from __future__ import annotations

from typing import Any

from discord import Interaction, ui, ButtonStyle


class OnboardWizard(ui.View):
    """Single-message stepper for collecting onboarding responses."""

    def __init__(
        self,
        controller: Any,
        *,
        thread_id: int | None,
        step: int = 0,
        timeout: float = 900,
    ) -> None:
        super().__init__(timeout=timeout)
        self.controller = controller
        self.thread_id = int(thread_id) if thread_id is not None else None
        self.step = int(step)
        self.add_item(self.BackBtn(self))
        self.add_item(self.NextBtn(self))
        self.add_item(self.CancelBtn(self))
        # Disable back button for the first step.
        if self.children:
            self.children[0].disabled = self.step <= 0

    async def _rerender(self, interaction: Interaction) -> None:
        content = self.controller.render_step(self.thread_id, self.step)
        await interaction.response.edit_message(content=content, view=self)

    class NextBtn(ui.Button):
        def __init__(self, parent: "OnboardWizard") -> None:
            super().__init__(
                label="Next ▶️",
                style=ButtonStyle.primary,
                custom_id="onboard.next",
            )
            self._view = parent

        async def callback(self, interaction: Interaction) -> None:  # pragma: no cover - driven by discord
            ctrl = self._view.controller
            thread_id = self._view.thread_id
            await ctrl.capture_step(interaction, thread_id, self._view.step)
            self._view.step += 1
            if ctrl.is_finished(thread_id, self._view.step):
                await ctrl.finish_and_summarize(interaction, thread_id)
                return
            if self._view.children:
                self._view.children[0].disabled = self._view.step <= 0
            await self._view._rerender(interaction)

    class BackBtn(ui.Button):
        def __init__(self, parent: "OnboardWizard") -> None:
            super().__init__(
                label="◀️ Back",
                style=ButtonStyle.secondary,
                custom_id="onboard.back",
            )
            self._view = parent

        async def callback(self, interaction: Interaction) -> None:  # pragma: no cover - driven by discord
            if self._view.step > 0:
                self._view.step -= 1
            if self._view.children:
                self._view.children[0].disabled = self._view.step <= 0
            await self._view._rerender(interaction)

    class CancelBtn(ui.Button):
        def __init__(self, parent: "OnboardWizard") -> None:
            super().__init__(
                label="Cancel",
                style=ButtonStyle.danger,
                custom_id="onboard.cancel",
            )
            self._view = parent

        async def callback(self, interaction: Interaction) -> None:  # pragma: no cover - driven by discord
            await interaction.response.edit_message(
                content=(
                    "Onboarding cancelled. You can press **Open questions** to start again."
                ),
                view=None,
            )
            controller = self._view.controller
            if hasattr(controller, "log_event"):
                await controller.log_event(
                    "info",
                    "onboard_cancelled",
                    thread_id=self._view.thread_id,
                )
