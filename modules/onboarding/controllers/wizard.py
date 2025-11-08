"""Controller for the onboarding wizard persistent panel."""

from __future__ import annotations

import asyncio
import re
from types import SimpleNamespace
from typing import Any

import discord
from discord.ext import commands

from modules.onboarding.sessions import Session
from modules.onboarding.ui import render as qrender
from modules.onboarding.ui import render_selects as srender
from modules.onboarding.ui import render_summary


class WizardController:
    """Coordinate onboarding wizard interactions for a single user session."""

    def __init__(self, bot: commands.Bot, sessions, renderer, config: Any | None = None) -> None:
        self.bot = bot
        self.sessions = sessions
        self.renderer = renderer
        self.log = getattr(bot, "logger", None)
        self.config = config or getattr(bot, "config", None)

        if self.config is None:
            self.config = SimpleNamespace()

    def _async_spawn(self, coro: Any) -> asyncio.Task:
        """Schedule ``coro`` on the bot loop."""

        loop = getattr(self.bot, "loop", None)
        if loop and loop.is_running():
            return loop.create_task(coro)
        return asyncio.create_task(coro)

    async def _send_or_edit_panel(
        self,
        interaction: discord.Interaction,
        session,
        *,
        content: str | None = None,
        view: discord.ui.View | None = None,
    ) -> None:
        """Single-message policy: always edit the same panel message."""

        if content is None or view is None:
            content, view = self.renderer.render(session)

        edit_count = 0
        followup_count = 0

        if not getattr(session, "panel_message_id", None):
            base_msg = getattr(interaction, "message", None)
            if base_msg is not None:
                session.panel_message_id = base_msg.id
                await base_msg.edit(content=content, view=view)
                edit_count += 1
            else:
                msg = await interaction.channel.send(content=content, view=view)
                session.panel_message_id = msg.id
                edit_count += 1
        else:
            try:
                msg = await interaction.channel.fetch_message(session.panel_message_id)
                await msg.edit(content=content, view=view)
                edit_count += 1
            except discord.NotFound:
                msg = await interaction.channel.send(content=content, view=view)
                session.panel_message_id = msg.id
                edit_count += 1

        await self.sessions.save(session)

        if self.log is not None:
            try:
                self.log.info(
                    "wizard:render",
                    extra={
                        "panel_message_id": session.panel_message_id,
                        "edit_count": edit_count,
                        "followup_count": followup_count,
                    },
                )
            except Exception:
                pass

    # ==== PR-B additions ====
    def _question_for_step(self, session) -> dict:
        """Return the question dict for the current step."""

        getter = getattr(self.renderer, "get_question", None)
        if getter is None:
            raise AttributeError("renderer missing get_question")
        return getter(session.step_index)

    def _has_question(self, index: int) -> bool:
        """Return True if a question exists at the given index without raising."""

        getter = getattr(self.renderer, "get_question", None)
        if getter is None:
            return False
        try:
            getter(index)
            return True
        except (IndexError, KeyError, TypeError):
            return False

    def _all_questions(self) -> list[dict]:
        """Return the full ordered question set for the renderer."""

        questions_callable = getattr(self.renderer, "all_questions", None)
        if callable(questions_callable):
            try:
                return list(questions_callable())
            except Exception:
                pass

        questions_attr = getattr(self.renderer, "questions", None)
        if isinstance(questions_attr, list):
            return list(questions_attr)

        questions: list[dict] = []
        index = 0
        while True:
            try:
                question = self.renderer.get_question(index)
            except (IndexError, KeyError, TypeError):
                break
            if not isinstance(question, dict) or not question:
                break
            questions.append(question)
            index += 1
        return questions

    def _is_required(self, question: dict) -> bool:
        value = str(question.get("required") or "").strip().upper()
        return value in {"TRUE", "1", "YES"}

    async def _render_current(self, interaction: discord.Interaction, session: Session) -> None:
        if getattr(session, "completed", False):
            try:
                await interaction.followup.send(
                    content="This onboarding has already been submitted.",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        question = self._question_for_step(session)
        required = self._is_required(question)
        has_answer = session.has_answer(question["gid"])
        optional = not required
        qtype = question.get("type")
        is_last = not self._has_question(session.step_index + 1)

        if qtype in {"short", "number", "paragraph", "bool"}:
            content, view = qrender.build_view(
                self,
                session,
                question,
                required=required,
                has_answer=has_answer,
                optional=optional,
                is_last=is_last,
            )
            await self._send_or_edit_panel(interaction, session, content=content, view=view)
            return

        if qtype in {"single-select", "multi-select"}:
            content, view = srender.build_view(
                self,
                session,
                question,
                required=required,
                has_answer=has_answer,
                optional=optional,
                is_last=is_last,
            )
            await self._send_or_edit_panel(interaction, session, content=content, view=view)
            return

        await self._send_or_edit_panel(interaction, session)

    async def _save_modal_answer(
        self,
        interaction: discord.Interaction,
        session: Session,
        question: dict,
        value: str,
    ) -> None:
        validate_rule = (question.get("validate") or "").strip()
        if validate_rule:
            try:
                if not re.fullmatch(validate_rule, value):
                    try:
                        await interaction.followup.send(
                            content="That doesn’t match the expected format.",
                            ephemeral=True,
                        )
                    except Exception:
                        pass
                    return
            except re.error:
                pass

        session.set_answer(question["gid"], value)

        if self.log:
            try:
                self.log.info(
                    "wizard:answer_saved",
                    extra={
                        "gid": question["gid"],
                        "kind": question.get("type"),
                        "required": self._is_required(question),
                    },
                )
            except Exception:
                pass

        await self._render_current(interaction, session)

    async def _save_bool_answer(
        self,
        interaction: discord.Interaction,
        session: Session,
        question: dict,
        value: bool,
    ) -> None:
        session.set_answer(question["gid"], value)

        if self.log:
            try:
                self.log.info(
                    "wizard:answer_saved",
                    extra={
                        "gid": question["gid"],
                        "kind": "bool",
                        "required": self._is_required(question),
                    },
                )
            except Exception:
                pass

        await self._render_current(interaction, session)

    async def _save_select_answer(
        self,
        interaction: discord.Interaction,
        session: Session,
        question: dict,
        value: str,
    ) -> None:
        session.set_answer(question["gid"], value)

        if self.log:
            try:
                self.log.info(
                    "wizard:answer_saved",
                    extra={
                        "gid": question["gid"],
                        "kind": "single",
                        "count": 1,
                        "required": self._is_required(question),
                    },
                )
            except Exception:
                pass

        await self._render_current(interaction, session)

    async def _save_multi_answer(
        self,
        interaction: discord.Interaction,
        session: Session,
        question: dict,
        values: list[str],
    ) -> None:
        session.set_answer(question["gid"], values)

        if self.log:
            try:
                self.log.info(
                    "wizard:answer_saved",
                    extra={
                        "gid": question["gid"],
                        "kind": "multi",
                        "count": len(values),
                        "required": self._is_required(question),
                    },
                )
            except Exception:
                pass

        await self._render_current(interaction, session)

    async def finish(self, interaction: discord.Interaction, session: Session) -> None:
        if getattr(session, "completed", False):
            try:
                await interaction.followup.send(
                    "This onboarding has already been submitted.",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        questions = self._all_questions()
        session.mark_completed()

        embed, answered = render_summary.build_summary_embed(session, questions)

        recruiter_role_id = getattr(self.config, "recruiter_role_id", None)
        ping_toggle = bool(getattr(self.config, "ping_recruiter", False))
        pinged = bool(ping_toggle and recruiter_role_id)
        content = ""
        if pinged:
            content = f"<@&{int(recruiter_role_id)}> New onboarding submission ready."

        await interaction.channel.send(content=content, embed=embed)

        if self.log:
            try:
                self.log.info(
                    "wizard:summary_posted",
                    extra={
                        "thread_id": interaction.channel.id,
                        "questions": answered,
                        "pinged": pinged,
                    },
                )
            except Exception:
                pass

        await self.sessions.save(session)

        try:
            await interaction.followup.send(
                "✅ All done — recruiter will review soon.",
                ephemeral=True,
            )
        except Exception:
            pass

    async def next(self, interaction: discord.Interaction, session: Session) -> None:
        question = self._question_for_step(session)
        if self._is_required(question) and not session.has_answer(question["gid"]):
            try:
                await interaction.followup.send(
                    content="Please answer this required question first.",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        # PR-B amend: don't run past final question
        next_index = session.step_index + 1
        if not self._has_question(next_index):
            await self.finish(interaction, session)
            return

        session.step_index = next_index
        await self._render_current(interaction, session)

    async def back(self, interaction: discord.Interaction, session: Session) -> None:
        if session.step_index > 0:
            session.step_index -= 1
        await self._render_current(interaction, session)

    async def skip(self, interaction: discord.Interaction, session: Session, question: dict) -> None:
        session.set_answer(question["gid"], "—")
        await self._render_current(interaction, session)

    async def cancel(self, interaction: discord.Interaction, session: Session) -> None:
        try:
            await interaction.followup.send(
                content="Onboarding cancelled. You can restart anytime.",
                ephemeral=True,
            )
        except Exception:
            pass

    async def launch(self, interaction: discord.Interaction) -> None:
        session = await self.sessions.load(interaction.channel.id, interaction.user.id)
        if getattr(session, "completed", False):
            try:
                await interaction.followup.send(
                    "This onboarding has already been submitted.",
                    ephemeral=True,
                )
            except Exception:
                pass
            return
        await self._render_current(interaction, session)

    async def restart(self, interaction: discord.Interaction) -> None:
        session = await self.sessions.load(interaction.channel.id, interaction.user.id)
        if getattr(session, "completed", False):
            try:
                await interaction.followup.send(
                    "This onboarding has already been submitted.",
                    ephemeral=True,
                )
            except Exception:
                pass
            return
        if hasattr(session, "reset"):
            session.reset()
        await self._render_current(interaction, session)
