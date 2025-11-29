"""Promo onboarding controller that mirrors the welcome controller."""

from __future__ import annotations

from discord.ext import commands

from modules.onboarding.controllers.welcome_controller import BaseWelcomeController


class PromoController(BaseWelcomeController):
    """Render the promo onboarding dialog."""

    def __init__(self, bot: commands.Bot, *, flow: str = "promo") -> None:
        super().__init__(bot, flow=flow)

    def session_status(self, thread_id: int) -> str | None:
        """Promo wizard hook used by BaseWelcomeController.render_step.

        Returning None keeps the nav logic in BaseWelcomeController using
        the standard is_session_completed() path without blowing up.
        """
        return None

    def _modal_title_prefix(self) -> str:
        return "Promo questions"

    def _modal_intro_text(self) -> str:
        return "🎉 Hold on we´ll be ready for you in a second."

    def _select_intro_text(self) -> str:
        return "🎯 Choose the options that apply for this promo."


__all__ = ["PromoController"]
