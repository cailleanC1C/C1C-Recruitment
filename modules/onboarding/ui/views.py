from __future__ import annotations

import logging
from typing import Optional

import discord

from modules.onboarding import diag

log = logging.getLogger("c1c.onboarding.ui.views")


class CleanLaunchView(discord.ui.View):
    def __init__(self, controller, thread_id: int | None, *, timeout: Optional[float] = 300) -> None:
        super().__init__(timeout=timeout)
        self.controller = controller
        self.thread_id = thread_id
        self.add_item(self.OpenButton(self))

    class OpenButton(discord.ui.Button):
        def __init__(self, parent: "CleanLaunchView") -> None:
            super().__init__(
                label="Open questions",
                style=discord.ButtonStyle.primary,
                custom_id="welcome.panel.start.clean",
            )
            self.parent = parent

        async def callback(self, interaction: discord.Interaction) -> None:
            controller = self.parent.controller
            thread_id = self.parent.thread_id

            if controller is None or thread_id is None:
                if diag.is_enabled():
                    await diag.log_event(
                        "warning",
                        "modal_launch_failed_clean",
                        thread_id=thread_id,
                        error="missing_controller",
                    )
                log.warning("clean launch missing controller or thread id")
                return

            preload_questions = getattr(controller, "get_or_load_questions", None)
            cache: list | None = None
            cache_dict = getattr(controller, "_questions", None)
            if isinstance(cache_dict, dict):
                cache = cache_dict.get(thread_id)
            else:
                legacy_cache = getattr(controller, "questions_by_thread", None)
                if isinstance(legacy_cache, dict):
                    cache = legacy_cache.get(thread_id)

            if callable(preload_questions) and not cache:
                try:
                    await preload_questions(thread_id)
                except Exception as exc:  # pragma: no cover - best-effort preload
                    if diag.is_enabled():
                        await diag.log_event(
                            "warning",
                            "onboard_preload_failed",
                            thread_id=thread_id,
                            error=str(exc),
                        )
                    log.warning("welcome modal preload failed (clean launch)", exc_info=True)

            try:
                modal = controller.build_modal_stub(thread_id)
            except Exception as exc:
                if diag.is_enabled():
                    await diag.log_event(
                        "warning",
                        "modal_build_failed_clean",
                        thread_id=thread_id,
                        error=str(exc),
                    )
                log.warning("failed to build modal stub for clean launch", exc_info=True)
                return

            try:
                await interaction.response.send_modal(modal)
            except discord.InteractionResponded:
                return
            except Exception as exc:  # pragma: no cover - defensive network operations
                if diag.is_enabled():
                    await diag.log_event(
                        "warning",
                        "modal_launch_failed_clean",
                        thread_id=thread_id,
                        error=str(exc),
                    )
                log.warning("clean launch send_modal failed", exc_info=True)
                return

            if diag.is_enabled():
                await diag.log_event(
                    "info",
                    "modal_launch_sent_clean",
                    thread_id=thread_id,
                    index=getattr(modal, "step_index", getattr(modal, "_c1c_index", 0)),
                )


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
                await self.parent.controller.render_inline_step(
                    interaction, self.parent.thread_id
                )
            except Exception:
                log.warning("failed to render inline step for next step", exc_info=True)
                if not interaction.response.is_done():
                    try:
                        await interaction.response.send_message(
                            "Couldn\u2019t open the questions just now. Please press the button again.",
                            ephemeral=True,
                        )
                    except Exception:
                        log.warning("failed to notify user about next-step error", exc_info=True)
                return


class RetryStartView(discord.ui.View):
    def __init__(self, controller, thread_id: int, *, timeout: Optional[float] = 300) -> None:
        super().__init__(timeout=timeout)
        self.controller = controller
        self.thread_id = thread_id
        self.add_item(self.OpenButton(self))

    class OpenButton(discord.ui.Button):
        def __init__(self, parent: "RetryStartView") -> None:
            super().__init__(
                label="Open questions",
                style=discord.ButtonStyle.primary,
                custom_id="welcome.panel.start.retry",
            )
            self.parent = parent

        async def callback(self, interaction: discord.Interaction) -> None:
            controller = self.parent.controller
            thread_id = self.parent.thread_id

            if controller is None or thread_id is None:
                await _notify_retry_failure(interaction)
                return

            try:
                await controller.render_inline_step(interaction, thread_id)
            except Exception:
                log.warning("failed to render inline step for retry start", exc_info=True)
                await _notify_retry_failure(interaction)
                return


async def _notify_retry_failure(interaction: discord.Interaction) -> None:
    response = getattr(interaction, "response", None)
    if response is None:
        return

    is_done = getattr(response, "is_done", None)
    already_done = False
    if callable(is_done):
        try:
            already_done = bool(is_done())
        except Exception:
            already_done = False
    elif isinstance(is_done, bool):
        already_done = is_done

    if already_done:
        return

    try:
        send_message = getattr(response, "send_message")
        if callable(send_message):
            await send_message(
                "Couldn’t open the questions just now. Please press the button again.",
                ephemeral=True,
            )
    except Exception:
        log.warning("failed to notify user about retry start error", exc_info=True)


__all__ = ["CleanLaunchView", "NextStepView", "RetryStartView"]
