"""Promo onboarding controller that mirrors the welcome controller."""

from __future__ import annotations

from discord.ext import commands

from .welcome_controller import BaseWelcomeController


class PromoController(BaseWelcomeController):
    """Render the promo onboarding dialog."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot, flow="promo")

    def _modal_title_prefix(self) -> str:
        return "Promo questions"

    def _modal_intro_text(self) -> str:
        return "🎉 Let's gather your promo details. Press the button below to begin."

    def _select_intro_text(self) -> str:
        return "🎯 Choose the options that apply for this promo."


__all__ = ["PromoController"]
