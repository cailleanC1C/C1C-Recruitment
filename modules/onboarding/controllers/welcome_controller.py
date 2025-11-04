"""Controller for the sheet-driven onboarding welcome flow."""

from __future__ import annotations

import asyncio
import logging
import math
import re
import sys
from typing import Any, Awaitable, Callable, Dict, Iterable, Mapping, Optional, Sequence, cast

import discord
from discord.ext import commands

from modules.onboarding import diag, logs, rules
from modules.onboarding.schema import (
    Question as SheetQuestionRecord,
    get_cached_welcome_questions,
    load_welcome_questions,
    parse_values_list,
)
from modules.onboarding.session_store import SessionData, store
from modules.onboarding.ui.modal_renderer import WelcomeQuestionnaireModal, build_modals
from modules.onboarding.ui.select_renderer import build_select_view
from modules.onboarding.ui.summary_embed import build_summary_embed
from modules.onboarding.ui.views import NextStepView
from modules.onboarding.ui import RollingCard, panels
from shared.config import get_onboarding_cleanup_after_summary
from shared.sheets.onboarding_questions import Question, schema_hash
from modules.common.logs import channel_label, user_label, log as shared_log

log = logging.getLogger(__name__)
gate_log = logging.getLogger("c1c.onboarding.gate")
launch_log = logging.getLogger("c1c.onboarding.controller")


# --- Sheet-driven validator (no fallbacks/coercion) --------------------------
NUMERIC_HINTS = ("number",)


def _sheet_regex(meta: dict[str, Any]) -> str | None:
    v = (meta.get("validate") or "").strip()
    if v.lower().startswith("regex:"):
        return v.split(":", 1)[1].strip()
    return None


def validate_answer(meta: dict[str, Any], raw: str) -> tuple[bool, str | None, str | None]:
    """
    (ok, cleaned, error)
    - If sheet provides a regex -> enforce it on the raw string.
    - Else -> accept as-is. No numeric/int fallbacks.
    """

    raw = "" if raw is None else str(raw)

    pattern = _sheet_regex(meta)
    if pattern:
        try:
            match = re.fullmatch(pattern, raw)
        except re.error:
            log.warning(
                "welcome: bad regex in sheet",
                extra={"qid": meta.get("qid"), "pattern": pattern},
            )
            return True, raw, None
        if not match:
            message = meta.get("help") or "Input does not match the required format."
            return False, None, message
        return True, raw, None

    return True, raw, None


def _display_name(user: discord.abc.User | discord.Member | None) -> str:
    if user is None:
        return "<unknown>"
    return (
        getattr(user, "display_name", None)
        or getattr(user, "global_name", None)
        or getattr(user, "name", None)
        or "<unknown>"
    )


def _channel_path(channel: discord.abc.GuildChannel | discord.Thread | None) -> str:
    if isinstance(channel, discord.Thread):
        parent = getattr(channel, "parent", None)
        parent_label = f"#{getattr(parent, 'name', 'unknown')}" if parent else "#unknown"
        return f"{parent_label} › {getattr(channel, 'name', 'thread')}"
    if isinstance(channel, discord.abc.GuildChannel):
        return f"#{getattr(channel, 'name', 'channel')}"
    return "#unknown"


def _log_gate(
    interaction: discord.Interaction,
    *,
    allowed: bool,
    reason: str,
    fallback_thread: discord.Thread | None = None,
) -> None:
    channel_obj: discord.abc.GuildChannel | discord.Thread | None
    channel_obj = interaction.channel if isinstance(interaction.channel, (discord.Thread, discord.abc.GuildChannel)) else fallback_thread
    emoji = "✅" if allowed else "🔐"
    status = "ok" if allowed else "deny"
    gate_log.info(
        "%s Welcome — gate=%s • user=%s • channel=%s • reason=%s",
        emoji,
        status,
        _display_name(getattr(interaction, "user", None)),
        _channel_path(channel_obj),
        reason,
    )


def _log_followup_fallback(
    interaction: discord.Interaction,
    *,
    action: str,
    error: Exception,
) -> None:
    gate_log.warning(
        "⚠️ Welcome — followup fallback • action=%s • user=%s • channel=%s • why=%s",
        action,
        _display_name(getattr(interaction, "user", None)),
        _channel_path(getattr(interaction, "channel", None)),
        getattr(error, "__class__", type(error)).__name__,
    )


async def _edit_deferred_response(interaction: discord.Interaction, message: str) -> None:
    try:
        await interaction.edit_original_response(content=message)
    except Exception as exc:  # pragma: no cover - defensive fallback
        _log_followup_fallback(interaction, action="edit_original", error=exc)
        followup = getattr(interaction, "followup", None)
        if followup is None:
            log.debug("followup handler missing; skipping deferred notice")
            return
        try:
            await followup.send(message, ephemeral=True)
        except Exception:  # pragma: no cover - final guard
            log.warning("failed to deliver followup message", exc_info=True)

_PANEL_RETRY_DELAYS = (0.5, 1.0, 2.0)

TEXT_TYPES = {"short", "paragraph", "number"}
SELECT_TYPES = {"single-select", "multi-select"}


class RollingCardSession:
    """Lightweight rolling-card flow for welcome text/number questions."""

    def __init__(
        self,
        controller: "WelcomeController",
        *,
        thread: discord.abc.Messageable,
        owner: discord.abc.User | discord.Member | None,
        guild: discord.Guild | None,
        questions: Sequence[SheetQuestionRecord],
    ) -> None:
        self.controller = controller
        self.thread = thread
        self.guild = guild or getattr(thread, "guild", None)
        self.card = RollingCard(thread)
        self.owner: discord.abc.User | discord.Member | None = (
            owner or getattr(thread, "owner", None)
        )
        identifier = getattr(self.owner, "id", None)
        if identifier is None:
            identifier = getattr(thread, "owner_id", None)
        try:
            self.owner_id: int | None = int(identifier) if identifier is not None else None
        except (TypeError, ValueError):
            self.owner_id = None
        self.thread_id: int | None = None
        thread_identifier = getattr(thread, "id", None)
        try:
            self.thread_id = int(thread_identifier) if thread_identifier is not None else None
        except (TypeError, ValueError):
            self.thread_id = None
        self._steps: list[SheetQuestionRecord] = [
            question for question in questions if self._supports(question)
        ]
        self._current_index = 0
        self._current_question: SheetQuestionRecord | None = None
        self._answers: dict[str, Any] = {}
        self._answer_order: list[SheetQuestionRecord] = []
        self._waiting = False
        self._closed = False

    @staticmethod
    def _supports(question: SheetQuestionRecord) -> bool:
        qtype = (question.qtype or "").lower()
        return qtype in {"bool"} or qtype.startswith(
            ("short", "paragraph", "number", "single-select", "multi-select")
        )

    def _owner_display_name(self) -> str:
        if self.owner is None:
            return "the ticket owner"
        return (
            getattr(self.owner, "display_name", None)
            or getattr(self.owner, "global_name", None)
            or getattr(self.owner, "name", None)
            or "the ticket owner"
        )

    def _is_owner(self, user: discord.abc.User | None) -> bool:
        if user is None:
            return False
        identifier = getattr(user, "id", None)
        try:
            value = int(identifier) if identifier is not None else None
        except (TypeError, ValueError):
            return False
        if self.owner_id is None and value is not None:
            self.owner_id = value
            self.owner = user
        return value is not None and value == self.owner_id

    async def close(self, *, reason: str | None = None) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            message = await self.card.ensure()
        except Exception:
            message = None
        if message is not None:
            try:
                await message.edit(view=None)
            except Exception:
                pass
        self.controller._complete_rolling(self.thread_id)
        captured = getattr(self.controller, "_captured_msgs", None)
        if captured is not None and self.thread_id is not None:
            captured.pop(int(self.thread_id), None)

    async def start(self) -> None:
        if self._closed:
            return
        if not self._steps:
            message = await self.card.ensure()
            await message.edit(content="**Onboarding — Completed**", view=None)
            self._closed = True
            self.controller._complete_rolling(self.thread_id)
            return
        await self._render_step()

    async def _render_step(self) -> None:
        if self._closed:
            return
        if self._current_index >= len(self._steps):
            await self._finish()
            return
        question = self._steps[self._current_index]
        self._current_question = question
        self._waiting = False
        view = self._view_for_question(question)
        await self.card.render(
            self._current_index + 1,
            len(self._steps),
            question.label,
            question.help,
            self._summary_lines(),
            view,
        )

    def _summary_lines(self) -> list[str]:
        lines = []
        for question in self._answer_order:
            value = self._answers.get(question.qid)
            if value is None:
                continue
            label = question.label or question.qid
            lines.append(f"• **{label}:** {self._value_for_summary(value)}")
        return lines

    def _view_for_question(self, question: SheetQuestionRecord) -> discord.ui.View:
        qtype = (question.qtype or "").lower()
        if qtype == "bool":
            return self._bool_view(question)
        if qtype.startswith("single-select") or qtype.startswith("multi-select"):
            view = self._select_view(question)
            if view is not None:
                return view
        return self._enter_view(question)

    def _enter_view(self, question: SheetQuestionRecord) -> discord.ui.View:
        session = self

        class EnterAnswerView(discord.ui.View):
            def __init__(self) -> None:
                super().__init__(timeout=None)

            @discord.ui.button(
                label="Enter answer",
                style=discord.ButtonStyle.primary,
                custom_id=f"welcome.card.enter:{question.qid}",
            )
            async def _enter(  # type: ignore[override]
                self, interaction: discord.Interaction, _: discord.ui.Button
            ) -> None:
                await session._handle_enter(interaction)

        return EnterAnswerView()

    def _bool_view(self, question: SheetQuestionRecord) -> discord.ui.View:
        session = self

        async def submit(interaction: discord.Interaction, choice: str) -> None:
            if not session._is_owner(getattr(interaction, "user", None)):
                try:
                    await interaction.response.send_message(
                        "Only the ticket owner can answer.", ephemeral=True
                    )
                except Exception:
                    pass
                return
            try:
                await interaction.response.defer()
            except discord.InteractionResponded:
                pass
            await session._store_answer_and_advance(question, choice)

        class BoolView(discord.ui.View):
            def __init__(self) -> None:
                super().__init__(timeout=None)

            @discord.ui.button(
                label="Yes",
                style=discord.ButtonStyle.success,
                custom_id=f"welcome.card.bool:{question.qid}:yes",
            )
            async def yes(  # type: ignore[override]
                self, interaction: discord.Interaction, _: discord.ui.Button
            ) -> None:
                await submit(interaction, "Yes")

            @discord.ui.button(
                label="No",
                style=discord.ButtonStyle.danger,
                custom_id=f"welcome.card.bool:{question.qid}:no",
            )
            async def no(  # type: ignore[override]
                self, interaction: discord.Interaction, _: discord.ui.Button
            ) -> None:
                await submit(interaction, "No")

        return BoolView()

    def _select_view(self, question: SheetQuestionRecord) -> discord.ui.View | None:
        options = parse_values_list(question.validate)
        if not options:
            options = [
                part.strip()
                for part in (question.note or "").split(",")
                if part.strip()
            ]
        if not options:
            return None

        qtype = (question.qtype or "").lower()
        max_values = 1
        if qtype.startswith("multi-select"):
            max_values = 3
            parts = [token for token in qtype.split("-") if token]
            for token in reversed(parts):
                if token.isdigit():
                    try:
                        max_values = max(1, int(token))
                    except (TypeError, ValueError):
                        max_values = 3
                    break
        max_values = min(max_values, len(options)) or 1

        session = self

        async def submit(interaction: discord.Interaction, values: list[str]) -> None:
            if not session._is_owner(getattr(interaction, "user", None)):
                try:
                    await interaction.response.send_message(
                        "Only the ticket owner can answer.", ephemeral=True
                    )
                except Exception:
                    pass
                return
            try:
                await interaction.response.defer()
            except discord.InteractionResponded:
                pass
            payload: Any
            if max_values > 1:
                payload = list(values)
            else:
                payload = values[0] if values else ""
            await session._store_answer_and_advance(question, payload)

        class SelectPrompt(discord.ui.View):
            def __init__(self) -> None:
                super().__init__(timeout=None)
                self.add_item(self._build_select())

            def _build_select(self) -> discord.ui.Select:
                class AnswerSelect(discord.ui.Select):
                    async def callback(self, interaction: discord.Interaction) -> None:
                        await submit(interaction, list(self.values))

                select = AnswerSelect(
                    placeholder="Select…",
                    min_values=1,
                    max_values=max_values,
                    options=[
                        discord.SelectOption(label=option, value=option)
                        for option in options
                    ],
                )
                return select

        return SelectPrompt()

    async def _handle_enter(self, interaction: discord.Interaction) -> None:
        if not self._is_owner(getattr(interaction, "user", None)):
            try:
                await interaction.response.send_message(
                    "Only the ticket owner can answer.", ephemeral=True
                )
            except Exception:
                pass
            return
        self._waiting = True
        owner_name = self._owner_display_name()
        view = discord.ui.View(timeout=None)
        view.add_item(
            discord.ui.Button(
                label=f"Waiting for {owner_name}…",
                disabled=True,
                style=discord.ButtonStyle.secondary,
            )
        )
        try:
            await interaction.response.edit_message(view=view)
        except discord.InteractionResponded:
            await interaction.edit_original_response(view=view)
        self._log_event("⌛", "waiting")

    def _value_tokens(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []
        if isinstance(value, Mapping):
            tokens: list[str] = []
            label = value.get("label") or value.get("value")
            if isinstance(label, str) and label.strip():
                tokens.append(label.strip())
            nested = value.get("values")
            if isinstance(nested, Iterable) and not isinstance(nested, (str, bytes, bytearray)):
                for item in nested:
                    tokens.extend(self._value_tokens(item))
            return tokens
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
            tokens: list[str] = []
            for item in value:
                tokens.extend(self._value_tokens(item))
            return tokens
        text = str(value).strip()
        return [text] if text else []

    def _value_for_summary(self, value: Any) -> str:
        tokens = self._value_tokens(value)
        if tokens:
            return ", ".join(tokens)
        return str(value)

    def _value_for_store(self, value: Any) -> str:
        tokens = self._value_tokens(value)
        if tokens:
            return ", ".join(tokens)
        return str(value)

    def _answers_by_qid(self) -> dict[str, Any]:
        return dict(self._answers)

    async def _store_answer_and_advance(
        self,
        question: SheetQuestionRecord,
        value: Any,
        *,
        source_message_id: int | None = None,
    ) -> None:
        self._answers[question.qid] = value
        if question not in self._answer_order:
            self._answer_order.append(question)
        str_value = self._value_for_store(value)
        try:
            self.controller._record_rolling_answer(self.thread_id, question, str_value)
        except Exception:
            pass
        captured = getattr(self.controller, "_captured_msgs", None)
        if (
            captured is not None
            and self.thread_id is not None
            and source_message_id is not None
        ):
            try:
                captured.setdefault(int(self.thread_id), []).append(int(source_message_id))
            except Exception:
                pass
        self._log_event("✅", "answer")
        answers_by_qid = self._answers_by_qid()
        try:
            jump = rules.next_index_by_rules(
                self._current_index, list(self._steps), answers_by_qid
            )
        except Exception:
            jump = None
        if jump is None:
            self._current_index += 1
        else:
            self._current_index = jump
        self._current_question = None
        self._waiting = False
        await self._render_step()

    async def handle_message(self, message: discord.Message) -> bool:
        if self._closed or not self._waiting or self._current_question is None:
            return False
        if self.thread_id is not None:
            channel_identifier = getattr(message.channel, "id", None)
            try:
                if int(channel_identifier) != self.thread_id:
                    return False
            except (TypeError, ValueError):
                return False
        if not self._is_owner(message.author):
            return False
        raw = (message.content or "").strip()
        question = self._current_question
        ok, cleaned, hint = self._validate(question, raw)
        if not ok:
            if hint:
                await self.card.hint(hint)
            self._log_event("❌", "invalid", detail=hint)
            return True
        await self._store_answer_and_advance(
            question,
            cleaned,
            source_message_id=getattr(message, "id", None),
        )
        return True

    def _log_event(self, emoji: str, event: str, *, detail: str | None = None) -> None:
        if self.thread_id is None:
            return
        guild_obj = self.guild or getattr(self.thread, "guild", None)
        launch_log.info(
            "%s Onboarding — %s • user=%s • thread=%s • qid=%s%s",
            emoji,
            event,
            user_label(guild_obj, self.owner_id),
            channel_label(guild_obj, self.thread_id),
            getattr(self._current_question, "qid", "unknown"),
            f" • {detail}" if detail else "",
        )

    async def _finish(self) -> None:
        self._current_question = None
        message = await self.card.ensure()
        summary = self._summary_lines()
        content = "**Onboarding — Completed**"
        if summary:
            content += "\n" + "\n".join(summary)
        try:
            await message.edit(content=content, view=None)
        except Exception:
            pass
        await self._cleanup_captured_messages()
        self._closed = True
        self.controller._complete_rolling(self.thread_id)

    async def _cleanup_captured_messages(self) -> None:
        if self.thread_id is None:
            return
        if not get_onboarding_cleanup_after_summary():
            return
        captured = getattr(self.controller, "_captured_msgs", None)
        if not isinstance(captured, dict):
            return
        thread_key = int(self.thread_id)
        message_ids = list(captured.get(thread_key, []))
        if not message_ids:
            captured.pop(thread_key, None)
            return
        fetcher = getattr(self.thread, "fetch_message", None)
        if not callable(fetcher):
            captured.pop(thread_key, None)
            return
        for message_id in message_ids:
            try:
                fetched = await fetcher(message_id)
            except Exception:
                continue
            try:
                await fetched.delete()
            except Exception:
                pass
        captured.pop(thread_key, None)

    def _validate(
        self, question: SheetQuestionRecord, value: str
    ) -> tuple[bool, str, str | None]:
        if (question.qtype or "").lower().startswith("number"):
            return self._validate_number(question, value)
        return self._validate_text(question, value)

    def _validate_text(
        self, question: SheetQuestionRecord, value: str
    ) -> tuple[bool, str, str | None]:
        cleaned = value.strip()
        maxlen = question.maxlen or 0
        if maxlen and len(cleaned) > maxlen:
            return False, cleaned, f"Max {maxlen} characters."
        validate = (question.validate or "").strip()
        if validate.lower().startswith("regex:"):
            pattern = validate.split(":", 1)[1].strip()
            if pattern:
                try:
                    if not re.fullmatch(pattern, cleaned):
                        return False, cleaned, "Format doesn’t match expected pattern."
                except re.error:
                    log.warning(
                        "rolling_card: invalid regex",
                        extra={"qid": question.qid, "pattern": pattern},
                    )
        return True, cleaned, None

    def _validate_number(
        self, question: SheetQuestionRecord, value: str
    ) -> tuple[bool, str, str | None]:
        cleaned = value.strip()
        if not cleaned:
            return False, cleaned, "Numbers only (e.g., 71)."
        enforce_int, min_value, max_value, step = self._parse_numeric_bounds(question.validate)
        try:
            number = int(cleaned) if enforce_int else float(cleaned)
        except ValueError:
            return False, cleaned, "Numbers only (e.g., 71)."
        if (min_value is not None and number < min_value) or (
            max_value is not None and number > max_value
        ):
            if min_value is not None and max_value is not None:
                return (
                    False,
                    cleaned,
                    f"Number must be between {self._fmt_number(min_value, enforce_int)} and {self._fmt_number(max_value, enforce_int)}.",
                )
            if min_value is not None:
                return (
                    False,
                    cleaned,
                    f"Number must be at least {self._fmt_number(min_value, enforce_int)}.",
                )
            return (
                False,
                cleaned,
                f"Number must be at most {self._fmt_number(max_value, enforce_int)}.",
            )
        if step and min_value is not None:
            base = min_value
        else:
            base = 0
        if step:
            remainder = (number - base) / step
            if not math.isclose(remainder, round(remainder), rel_tol=1e-9, abs_tol=1e-9):
                return False, cleaned, f"Number must increase by steps of {self._fmt_number(step, enforce_int)}."
        return True, cleaned, None

    @staticmethod
    def _fmt_number(value: float, enforce_int: bool) -> str:
        if enforce_int:
            return str(int(value))
        return ("%g" % value).rstrip("0").rstrip(".") if isinstance(value, float) else str(value)

    @staticmethod
    def _parse_numeric_bounds(
        validate: str | None,
    ) -> tuple[bool, float | None, float | None, float | None]:
        if not validate:
            return False, None, None, None
        text = validate.strip()
        enforce_int = text.lower().startswith("int")
        remainder = text
        if ":" in text:
            prefix, suffix = text.split(":", 1)
            if prefix.lower() == "int":
                remainder = suffix
        tokens = re.split(r"[;,]", remainder)
        min_value: float | None = None
        max_value: float | None = None
        step: float | None = None
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            match = re.match(r"(?i)(min|max|step)\s*=\s*(-?\d+(?:\.\d+)?)", token)
            if not match:
                continue
            key = match.group(1).lower()
            try:
                value = float(match.group(2))
            except ValueError:
                continue
            if key == "min":
                min_value = value
            elif key == "max":
                max_value = value
            elif key == "step":
                step = value
        return enforce_int, min_value, max_value, step
async def locate_welcome_message(thread: discord.Thread) -> discord.Message | None:
    """Return the welcome greeting message for ``thread`` when available."""

    starter = getattr(thread, "starter_message", None)
    if starter is not None:
        return starter

    parent = getattr(thread, "parent", None)
    if parent is not None:
        parent_fetch = getattr(parent, "fetch_message", None)
        if callable(parent_fetch):
            try:
                return await parent_fetch(int(thread.id))
            except Exception:
                pass

    history = getattr(thread, "history", None)
    if callable(history):
        try:
            async for candidate in history(limit=5, oldest_first=True):
                return candidate
        except Exception:
            pass

    return None


def extract_target_from_message(
    message: discord.Message | None,
) -> tuple[int | None, int | None]:
    """Return ``(target_user_id, message_id)`` extracted from ``message``."""

    target_id: int | None = None
    message_id: int | None = None

    if message is None:
        return target_id, message_id

    raw_message_id = getattr(message, "id", None)
    if raw_message_id is not None:
        try:
            message_id = int(raw_message_id)
        except (TypeError, ValueError):
            message_id = None

    for user in getattr(message, "mentions", []) or []:
        if getattr(user, "bot", False):
            continue
        user_id = getattr(user, "id", None)
        if user_id is None:
            continue
        try:
            target_id = int(user_id)
        except (TypeError, ValueError):
            continue
        break

    return target_id, message_id


class BaseWelcomeController:
    """Shared orchestration logic for welcome/promo onboarding flows."""

    def __init__(self, bot: commands.Bot, *, flow: str) -> None:
        self.bot = bot
        self.flow = flow
        self._threads: Dict[int, discord.Thread] = {}
        self._questions: Dict[int, list[Question]] = {}
        self.questions_by_thread = self._questions
        self.answers_by_thread: Dict[int, dict[str, Any]] = {}
        self._select_messages: Dict[int, discord.Message] = {}
        self._preview_messages: Dict[int, discord.Message] = {}
        self._preview_logged: set[int] = set()
        self._sources: Dict[int, str] = {}
        self._allowed_users: Dict[int, set[int]] = {}
        self._panel_messages: Dict[int, int] = {}
        self._prefetched_panels: Dict[int, discord.Message] = {}
        self._initiators: Dict[int, discord.abc.User | discord.Member | None] = {}
        self._target_users: Dict[int, int | None] = {}
        self._target_message_ids: Dict[int, int | None] = {}
        self.retry_message_ids: Dict[int, int] = {}
        # Legacy alias for UI helpers that still look for ``questions_by_thread``.
        self.questions_by_thread = self._questions

    def _thread_for(self, thread_id: int) -> discord.Thread | None:
        return self._threads.get(thread_id)

    def diag_target_user_id(self, thread_id: int) -> int | None:
        """Return the cached target recruit identifier for diagnostics."""

        return self._target_users.get(thread_id)

    @staticmethod
    def _question_key(question: Question | dict[str, Any]) -> str:
        if hasattr(question, "qid"):
            value = getattr(question, "qid")
            return str(value)
        if isinstance(question, dict):
            candidate = question.get("id") or question.get("qid")
            if candidate is not None:
                return str(candidate)
        return ""

    def _question_meta(self, question: Question | dict[str, Any]) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "qid": self._question_key(question),
            "label": "",
            "type": "",
            "validate": None,
            "help": None,
        }
        if isinstance(question, dict):
            meta["label"] = str(question.get("label") or question.get("text") or "")
            meta["type"] = str(question.get("type") or "")
            meta["validate"] = question.get("validate")
            meta["help"] = question.get("help")
        else:
            meta["label"] = str(getattr(question, "label", ""))
            meta["type"] = str(getattr(question, "type", ""))
            meta["validate"] = getattr(question, "validate", None)
            meta["help"] = getattr(question, "help", None)
        return meta

    def _has_sheet_regex(self, meta: dict[str, Any]) -> bool:
        return bool(_sheet_regex(meta))

    def validate_answer(self, meta: dict[str, Any], raw: str) -> tuple[bool, str | None, str | None]:
        return validate_answer(meta, raw)

    async def _send_validation_error(
        self,
        interaction: discord.Interaction,
        thread_id: int,
        meta: dict[str, Any],
        message: str | None,
    ) -> None:
        label = meta.get("label") or meta.get("qid") or "This question"
        notice = message or "Input does not match the required format."
        await _safe_ephemeral(interaction, f"⚠️ **{label}** • {notice}")

    def _answer_for(self, thread_id: int, key: str) -> Any:
        answers = self.answers_by_thread.get(thread_id)
        if answers and key in answers:
            return answers[key]
        session = store.get(thread_id)
        if session and session.answers:
            return session.answers.get(key)
        return None

    def _answer_present(self, question: Question | dict[str, Any], value: Any) -> bool:
        if value is None:
            return False
        qtype = getattr(question, "type", None)
        if isinstance(question, dict):
            qtype = question.get("type")
        if qtype in SELECT_TYPES:
            return _has_select_answer(value)
        if qtype == "number":
            return value is not None
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, dict):
            return bool(value)
        if isinstance(value, Iterable):
            return any(True for _ in value)
        return bool(value)

    async def set_answer(self, thread_id: int, key: str, value: Any) -> None:
        answers = self.answers_by_thread.setdefault(thread_id, {})
        if value is None or (isinstance(value, str) and not value.strip()):
            answers.pop(key, None)
        elif isinstance(value, (list, tuple)) and not value:
            answers.pop(key, None)
        elif isinstance(value, dict) and not value:
            answers.pop(key, None)
        else:
            answers[key] = value

        session = store.get(thread_id)
        if session is not None:
            session.answers = session.answers or {}
            if value is None or (isinstance(value, str) and not value.strip()):
                session.answers.pop(key, None)
            elif isinstance(value, (list, tuple)) and not value:
                session.answers.pop(key, None)
            elif isinstance(value, dict) and not value:
                session.answers.pop(key, None)
            else:
                session.answers[key] = value
            try:
                session.visibility = rules.evaluate_visibility(
                    self._questions.get(thread_id, []), session.answers
                )
            except Exception:
                log.warning("failed to recompute visibility during inline capture", exc_info=True)

    def has_answer(self, thread_id: int, question: Question | dict[str, Any]) -> bool:
        key = self._question_key(question)
        if not key:
            return False
        value = self._answer_for(thread_id, key)
        return self._answer_present(question, value)

    def is_finished(self, thread_id: int, step: int) -> bool:
        questions = self._questions.get(thread_id) or []
        return step >= len(questions)

    def render_step(self, thread_id: int, step: int) -> str:
        questions = self._questions.get(thread_id) or []
        if not questions:
            return "No onboarding questions are configured for this flow yet."
        if step < 0:
            step = 0
        if step >= len(questions):
            step = len(questions) - 1
        question = questions[step]
        label = getattr(question, "label", None) or str(question)
        key = self._question_key(question)
        stored = self._answer_for(thread_id, key)
        formatted = _preview_value_for_question(question, stored)
        if formatted:
            return f"{label}\n\nCurrent answer: {formatted}"
        return label

    async def finish_inline_wizard(
        self,
        thread_id: int,
        interaction: discord.Interaction,
        *,
        message: discord.Message | None = None,
    ) -> None:
        answers = self.answers_by_thread.get(thread_id, {})
        if message is None:
            message = getattr(interaction, "message", None)
        notice = "✅ Collected. Posting summary…"
        try:
            if interaction is not None and not interaction.response.is_done():
                await interaction.response.edit_message(content=notice, view=None)
            elif message is not None:
                await message.edit(content=notice, view=None)
        except Exception:
            log.warning("failed to update wizard completion message", exc_info=True)

        thread: discord.Thread | None = None
        if message is not None:
            channel = getattr(message, "channel", None)
            if isinstance(channel, discord.Thread):
                thread = channel
        if thread is None:
            thread = self._threads.get(thread_id)
        if thread is None:
            return

        session = store.get(thread_id)
        visibility = None
        if session is not None:
            session.answers = dict(answers)
            visibility = session.visibility
        else:
            session = store.ensure(thread_id, flow=self.flow, schema_hash=schema_hash(self.flow))
            session.answers = dict(answers)
            visibility = session.visibility

        try:
            summary_author = self._resolve_summary_author(thread, interaction)
        except Exception:
            log.warning("failed to resolve summary author; falling back to thread owner", exc_info=True)
            summary_author = getattr(thread, "owner", None) or interaction.user

        schema = session.schema_hash if session else schema_hash(self.flow)
        summary_embed = build_summary_embed(
            self.flow,
            dict(answers),
            summary_author,
            schema or "",
            visibility,
        )

        recruiter_ids = list(getattr(self, "recruiter_role_ids", []) or [])
        if not recruiter_ids:
            recruiter_ids = list(getattr(self, "RECRUITER_ROLE_IDS", []) or [])
        mention_text = " ".join(f"<@&{int(role_id)}>" for role_id in recruiter_ids if role_id)
        allowed_mentions = discord.AllowedMentions(roles=True, users=False, everyone=False)
        try:
            await thread.send(
                content=mention_text or None,
                embed=summary_embed,
                allowed_mentions=allowed_mentions if mention_text else None,
            )
        except Exception:
            log.warning("failed to post onboarding summary", exc_info=True)
        else:
            await logs.send_welcome_log(
                "info",
                result="completed",
                view="inline",
                source=self._sources.get(thread_id, "unknown"),
                schema=session.schema_hash if session else None,
                details=_final_fields(self._questions.get(thread_id, []), dict(answers)),
                **self._log_fields(thread_id, actor=getattr(interaction, "user", None)),
            )

        self.answers_by_thread.pop(thread_id, None)
        self._cleanup_session(thread_id)

    def _log_fields(
        self,
        thread_id: int,
        *,
        actor: discord.abc.User | discord.Member | None | object = ...,
    ) -> dict[str, Any]:
        thread = self._thread_for(thread_id)
        context = logs.thread_context(thread)
        context["flow"] = self.flow
        resolved_actor: discord.abc.User | discord.Member | None
        if actor is ...:
            resolved_actor = self._initiators.get(thread_id)
        else:
            resolved_actor = cast(discord.abc.User | discord.Member | None, actor)
        context["actor"] = logs.format_actor(resolved_actor)
        handle = logs.format_actor_handle(resolved_actor)
        if handle:
            context["actor_name"] = handle
        return context

    async def _send_panel_with_retry(
        self,
        thread: discord.Thread,
        *,
        content: str,
        view: discord.ui.View,
    ) -> discord.Message:
        last_error: Exception | None = None
        for delay in (0.0, *_PANEL_RETRY_DELAYS):
            if delay:
                await asyncio.sleep(delay)
            try:
                message = await thread.send(content, view=view)
                if getattr(message, "pinned", False):
                    try:
                        await message.unpin()
                    except Exception:
                        log.warning("failed to unpin welcome panel", exc_info=True)
                return message
            except Exception as exc:  # pragma: no cover - network
                last_error = exc
        assert last_error is not None  # for mypy
        await logs.send_welcome_exception(
            "error",
            last_error,
            **self._log_fields(int(thread.id), result="panel_failed"),
        )
        raise last_error

    async def run(
        self,
        thread: discord.Thread,
        initiator: discord.abc.User | discord.Member | None,
        schema_hash: str | None,
        questions: Sequence[Question],
        *,
        source: str,
    ) -> None:
        thread_id = int(thread.id)
        session = store.ensure(thread_id, flow=self.flow, schema_hash=schema_hash)
        session.answers = session.answers or {}
        session.visibility = rules.evaluate_visibility(questions, session.answers)
        self._threads[thread_id] = thread
        self._questions[thread_id] = list(questions)
        self._sources[thread_id] = source
        self._initiators[thread_id] = initiator
        panels.bind_controller(thread_id, self)

        allowed_ids: set[int] = set()
        self._allowed_users[thread_id] = allowed_ids

        await self._ensure_target_cached(thread_id)
        target_id = self._target_users.get(thread_id)
        if target_id is not None:
            allowed_ids.add(int(target_id))

        await self._start_modal_step(thread, session)

    async def _start_modal_step(
        self,
        thread: discord.Thread,
        session: SessionData,
        *,
        anchor: discord.Message | None = None,
    ) -> None:
        thread_id = int(thread.id)
        if anchor is None:
            anchor = self._prefetched_panels.pop(thread_id, None)
        modals = build_modals(
            self._questions[thread_id],
            session.visibility,
            session.answers,
            title_prefix=self._modal_title_prefix(),
        )
        if not modals:
            await self._start_select_step(thread, session)
            return

        store.set_pending_step(thread_id, {"kind": "inline", "index": 0})
        intro = self._modal_intro_text()
        view = panels.OpenQuestionsPanelView(controller=self, thread_id=thread_id)
        message_id = self._panel_messages.get(thread_id)
        message: discord.Message | None = None
        if anchor is not None:
            message = anchor
            anchor_id = getattr(anchor, "id", None)
            if anchor_id is not None:
                try:
                    self._panel_messages[thread_id] = int(anchor_id)
                except (TypeError, ValueError):
                    pass

        parent_channel = getattr(thread, "parent", None)
        try:
            parent_id_int = int(parent_channel.id) if parent_channel is not None else None
        except (TypeError, ValueError, AttributeError):
            parent_id_int = None

        base_log = self._log_fields(thread_id)
        base_log.update(
            {
                "view": "panel",
                "view_tag": panels.WELCOME_PANEL_TAG,
                "custom_id": panels.OPEN_QUESTIONS_CUSTOM_ID,
                "diag": base_log.get("diag") or f"{self.flow}_flow",
                "flow": self.flow,
                "thread_id": thread_id,
            }
        )
        if parent_id_int is not None:
            base_log.setdefault("parent_id", parent_id_int)
            base_log.setdefault("parent_channel_id", parent_id_int)

        posted_new_message = False

        if message is None and message_id:
            try:
                message = await thread.fetch_message(message_id)
            except discord.NotFound as exc:
                error_text = f"{exc.__class__.__name__}: {exc}"
                try:
                    stale_message_id = int(message_id)
                except (TypeError, ValueError):
                    stale_message_id = None
                stale_context = dict(base_log)
                stale_context.update(
                    {
                        "event": "stale_panel",
                        "result": "stale_panel",
                        "message_id": stale_message_id,
                        "error": error_text,
                        "details": "view=panel; source=emoji",
                    }
                )
                await logs.send_welcome_log("warn", **stale_context)

                try:
                    message = await self._send_panel_with_retry(thread, content=intro, view=view)
                except Exception:
                    return
                posted_new_message = True
                message_id = int(message.id)
                self._panel_messages[thread_id] = message_id
            except Exception as exc:
                error_context = dict(base_log)
                try:
                    error_context.setdefault("message_id", int(message_id))
                except (TypeError, ValueError):
                    pass
                error_context.update(
                    {
                        "event": "stale_panel",
                        "result": "stale_panel",
                    }
                )
                await logs.send_welcome_exception("warn", exc, **error_context)

        if message is None:
            try:
                message = await self._send_panel_with_retry(thread, content=intro, view=view)
            except Exception:
                return
            posted_new_message = True
            self._panel_messages[thread_id] = message.id
            message_id = int(message.id)
        else:
            message_id = int(getattr(message, "id", message_id))
            if not posted_new_message:
                await message.edit(content=intro, view=view)
                if getattr(message, "pinned", False):
                    try:
                        await message.unpin()
                    except Exception:
                        log.warning("failed to unpin welcome panel", exc_info=True)

        panels.register_panel_message(thread_id, message.id)

        panel_log_context = dict(base_log)
        panel_log_context.update(
            {
                "event": "panel_posted",
                "result": "posted" if posted_new_message else "refreshed",
                "source": self._sources.get(thread_id),
                "message_id": int(message.id),
                "custom_id": panels.OPEN_QUESTIONS_CUSTOM_ID,
                "view_timeout": view.timeout,
                "disable_on_timeout": getattr(view, "disable_on_timeout", None),
            }
        )
        await logs.send_welcome_log(
            "info" if posted_new_message else "debug",
            **panel_log_context,
        )
        if diag.is_enabled():
            parent_id = getattr(thread, "parent_id", None)
            try:
                parent_id_int = int(parent_id) if parent_id is not None else None
            except (TypeError, ValueError):
                parent_id_int = None
            target_user_id = self._target_users.get(thread_id)
            await diag.log_event(
                "info",
                "panel_posted",
                message_id=int(message.id),
                thread_id=thread_id,
                parent_id=parent_id_int,
                schema_id=session.schema_hash,
                custom_id=panels.OPEN_QUESTIONS_CUSTOM_ID,
                view_timeout=view.timeout,
                disable_on_timeout=getattr(view, "disable_on_timeout", None),
                target_user_id=target_user_id,
                ambiguous_target=target_user_id is None,
            )

    async def _start_select_step(self, thread: discord.Thread, session: SessionData) -> None:
        thread_id = int(thread.id)
        async def gate(interaction: discord.Interaction) -> bool:
            allowed, _ = await self.check_interaction(thread_id, interaction)
            return allowed

        pending = session.pending_step or {}
        page = int(pending.get("page", 0))
        view = build_select_view(
            self._questions[thread_id],
            session.visibility,
            session.answers,
            interaction_check=gate,
            page=page,
        )
        if view is None:
            await self._show_preview(thread, session)
            return

        view.on_change = self._select_changed(thread_id)
        view.on_complete = self._select_completed(thread_id)
        view.on_page_change = self._select_page_updated(thread_id)
        store.set_pending_step(thread_id, {"kind": "select", "index": 0, "page": view.page})
        content = self._select_intro_text()
        message = self._select_messages.get(thread_id)
        if message:
            await message.edit(content=content, view=view)
        else:
            message = await thread.send(content, view=view)
            self._select_messages[thread_id] = message
        await logs.send_welcome_log(
            "debug",
            view="select",
            result="ready",
            **self._log_fields(thread_id),
        )

    def build_modal_stub(self, thread_id: int, *, index: Optional[int] = None) -> WelcomeQuestionnaireModal:
        session = store.get(thread_id)
        questions = self._questions.get(thread_id)
        answers = session.answers if session else {}
        visibility = session.visibility if session else {}
        pending = session.pending_step or {} if session else {}
        step_index = index if index is not None else int(pending.get("index", 0) or 0)

        modals = build_modals(
            questions or [],
            visibility,
            answers,
            title_prefix=self._modal_title_prefix(),
        )

        if modals:
            if step_index < 0:
                step_index = 0
            if step_index >= len(modals):
                step_index = len(modals) - 1
            modal = modals[step_index]
            modal.submit_callback = self._modal_submitted(thread_id, list(modal.questions), modal.step_index)
        else:
            modal = WelcomeQuestionnaireModal(
                questions=[],
                step_index=0,
                total_steps=1,
                title_prefix=self._modal_title_prefix(),
                answers=answers,
                visibility=visibility,
                on_submit=self._modal_submitted(thread_id, [], 0),
            )

        setattr(modal, "_c1c_thread_id", thread_id)
        setattr(modal, "_c1c_index", getattr(modal, "step_index", 0))
        return modal

    async def get_or_load_questions(
        self,
        thread_id: int,
        *,
        session: SessionData | None = None,
    ) -> list[Question] | None:
        questions = self._questions.get(thread_id)
        if questions:
            return questions
        restored = await self._rehydrate_questions(thread_id, session=session)
        if restored:
            return self._questions.get(thread_id)
        return None

    async def prompt_retry(self, interaction: discord.Interaction, thread_id: int) -> None:
        thread = self._threads.get(thread_id)
        if thread is None and isinstance(interaction.channel, discord.Thread):
            thread = interaction.channel
        if thread is None:
            return
        try:
            await thread.send("Something blinked. Tap **Open questions** again to continue.")
        except Exception:
            log.warning("failed to post retry prompt", exc_info=True)

    async def prompt_next(self, interaction: discord.Interaction, thread_id: int, next_idx: int) -> None:
        thread = self._threads.get(thread_id)
        if thread is None and isinstance(interaction.channel, discord.Thread):
            thread = interaction.channel
        if thread is None:
            return
        view = self.make_next_button(thread_id, next_idx)
        try:
            await thread.send("Next up…", view=view)
        except Exception:
            log.warning("failed to post next-step prompt", exc_info=True)

    def make_next_button(self, thread_id: int, next_idx: int) -> NextStepView:
        return NextStepView(self, thread_id, next_idx)

    async def render_inline_step(
        self,
        interaction: discord.Interaction,
        thread_id: int,
        *,
        index: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        diag_state = diag.interaction_state(interaction)
        diag_state["thread_id"] = thread_id
        diag_state["view"] = "inline"
        data = getattr(interaction, "data", None)
        if isinstance(data, dict):
            diag_state["custom_id"] = data.get("custom_id")
        target_user_id = self._target_users.get(thread_id)
        diag_state["target_user_id"] = target_user_id
        diag_state["ambiguous_target"] = target_user_id is None

        response = getattr(interaction, "response", None)
        response_done = False
        if response is not None:
            is_done = getattr(response, "is_done", None)
            if callable(is_done):
                try:
                    response_done = bool(is_done())
                except Exception:
                    response_done = False
            elif isinstance(is_done, bool):
                response_done = is_done
        if response_done:
            diag_state["response_is_done"] = True
            if diag.is_enabled():
                await diag.log_event(
                    "warning",
                    "inline_launch_skipped",
                    skip_reason="interaction_already_responded",
                    **diag_state,
                )
            return

        session = store.get(thread_id)
        if session is None:
            session = store.ensure(thread_id, flow=self.flow, schema_hash=schema_hash(self.flow))

        try:
            questions_for_thread = await self.get_or_load_questions(thread_id, session=session)
        except Exception:
            log.warning("failed to load questions for inline wizard", exc_info=True)
            raise

        if not questions_for_thread:
            raise RuntimeError("no questions available for inline wizard")

        if not session.visibility:
            try:
                session.visibility = rules.evaluate_visibility(
                    questions_for_thread,
                    session.answers,
                )
            except Exception:
                session.visibility = {}

        pending = session.pending_step or {}
        if index is None:
            raw_index = pending.get("index", 0) if isinstance(pending, dict) else 0
            try:
                index = int(raw_index)
            except (TypeError, ValueError):
                index = 0
        total_questions = len(questions_for_thread)
        if total_questions <= 0:
            raise RuntimeError("no inline steps available")
        if index < 0:
            index = 0
        if index >= total_questions:
            index = total_questions - 1

        store.set_pending_step(thread_id, {"kind": "inline", "index": index})

        try:
            content = self.render_step(thread_id, index)
        except Exception:
            log.warning("failed to render inline step", exc_info=True)
            raise

        wizard = panels.OnboardWizard(self, thread_id, step=index)

        diag_state["step_index"] = index
        diag_state["total_steps"] = total_questions

        try:
            await interaction.response.send_message(content=content, view=wizard)
        except Exception as exc:
            if diag.is_enabled():
                await diag.log_event(
                    "warning",
                    "inline_launch_failed",
                    exception_type=exc.__class__.__name__,
                    exception_message=str(exc),
                    **diag_state,
                )
            raise
        else:
            if diag.is_enabled():
                await diag.log_event("info", "inline_wizard_posted", **diag_state)

        try:
            message = await interaction.original_response()
        except Exception:
            message = None
        if message is not None:
            wizard.attach(message)

        log_payload = self._log_fields(thread_id, actor=getattr(interaction, "user", None))
        if context is not None:
            log_payload.update(context)
        log_payload.setdefault("source", self._sources.get(thread_id, "unknown"))
        await logs.send_welcome_log(
            "debug",
            view="inline",
            result="launched",
            index=index,
            **log_payload,
        )

    async def finish_onboarding(
        self,
        interaction: discord.Interaction,
        thread_id: int,
        *,
        session: SessionData,
        thread: discord.Thread,
    ) -> None:
        await self._start_select_step(thread, session)
        refreshed = store.get(thread_id)
        pending = refreshed.pending_step if refreshed is not None else None
        if not pending:
            try:
                await thread.send("All set. A recruiter will review your answers shortly.")
            except Exception:
                log.warning("failed to send onboarding completion notice", exc_info=True)

    def _select_changed(self, thread_id: int) -> Callable[[discord.Interaction, Question, list[str]], Awaitable[None]]:
        async def handler(
            interaction: discord.Interaction,
            question: Question,
            values: list[str],
        ) -> None:
            allowed, _ = await self.check_interaction(thread_id, interaction)
            if not allowed:
                return
            await self._handle_select_change(thread_id, interaction, question, values)

        return handler

    def _select_completed(self, thread_id: int) -> Callable[[discord.Interaction], Awaitable[None]]:
        async def handler(interaction: discord.Interaction) -> None:
            allowed, _ = await self.check_interaction(thread_id, interaction)
            if not allowed:
                return
            await self._handle_select_complete(thread_id, interaction)

        return handler

    async def _handle_modal_launch(
        self,
        thread_id: int,
        interaction: discord.Interaction,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        await self.render_inline_step(interaction, thread_id, context=context)

    async def _rehydrate_questions(
        self,
        thread_id: int,
        *,
        session: SessionData | None,
    ) -> bool:
        """Best-effort attempt to restore question state for a thread."""

        questions = self._questions.get(thread_id)
        if questions:
            return True

        try:
            from shared.sheets import onboarding_questions
        except Exception:
            return False

        try:
            refreshed = onboarding_questions.get_questions(self.flow)
        except Exception:
            log.warning(
                "failed to rehydrate welcome questions", exc_info=True
            )
            return False

        self._questions[thread_id] = list(refreshed)
        if session is not None:
            try:
                session.visibility = rules.evaluate_visibility(
                    self._questions[thread_id],
                    session.answers,
                )
            except Exception:
                log.warning(
                    "failed to recompute visibility during welcome rehydrate",
                    exc_info=True,
                )
        return True

    async def _restart_from_interaction(
        self,
        thread_id: int,
        interaction: discord.Interaction,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        channel = interaction.channel if isinstance(interaction.channel, discord.Thread) else None
        thread = self._threads.get(thread_id) or channel
        message = getattr(interaction, "message", None)
        message_id = getattr(message, "id", None)

        log_payload = self._log_fields(thread_id, actor=interaction.user)
        if context is not None:
            log_payload.update(context)
        if thread is not None:
            log_payload.setdefault("thread", logs.format_thread(getattr(thread, "id", None)))
            parent_id = getattr(thread, "parent_id", None)
            if parent_id is not None:
                try:
                    log_payload.setdefault("parent_channel_id", int(parent_id))
                except (TypeError, ValueError):
                    pass
        if message_id is not None:
            try:
                log_payload.setdefault("message_id", int(message_id))
            except (TypeError, ValueError):
                pass
        log_payload["view"] = "panel"
        log_payload.setdefault("view_tag", panels.WELCOME_PANEL_TAG)
        log_payload.setdefault("custom_id", panels.OPEN_QUESTIONS_CUSTOM_ID)
        log_payload["result"] = "restarted"

        try:
            await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass
        except Exception:
            log.warning("failed to defer restart notice", exc_info=True)

        await logs.send_welcome_log("info", **log_payload)

        self._cleanup_session(thread_id)

        if thread is None:
            failure = dict(log_payload)
            failure["result"] = "error"
            failure["reason"] = "thread_missing"
            await logs.send_welcome_log("error", **failure)
            return

        try:
            from modules.onboarding.welcome_flow import start_welcome_dialog

            panel_message = message if isinstance(message, discord.Message) else None
            panel_id = None
            if message_id is not None:
                try:
                    panel_id = int(message_id)
                except (TypeError, ValueError):
                    panel_id = None
            await start_welcome_dialog(
                thread,
                interaction.user,
                "panel_restart",
                bot=self.bot,
                panel_message_id=panel_id,
                panel_message=panel_message,
            )
        except Exception as exc:  # pragma: no cover - network restart errors
            error_payload = dict(log_payload)
            error_payload["result"] = "error"
            await logs.send_welcome_exception("error", exc, **error_payload)

    def _modal_submitted(
        self,
        thread_id: int,
        questions: Sequence[Question],
        index: int,
    ) -> Callable[[discord.Interaction, dict[str, str]], Awaitable[None]]:
        async def handler(
            interaction: discord.Interaction,
            values: dict[str, str],
        ) -> None:
            await self._handle_modal_submit(thread_id, interaction, questions, index, values)

        return handler

    async def _handle_modal_submit(
        self,
        thread_id: int,
        interaction: discord.Interaction,
        questions: Sequence[Question],
        index: int,
        values: dict[str, str],
    ) -> None:
        session = store.get(thread_id)
        thread = self._threads.get(thread_id)
        await interaction.response.defer(ephemeral=True)

        if session is None or thread is None:
            await logs.send_welcome_log(
                "warn",
                view="modal",
                result="inactive",
                index=index,
                **self._log_fields(thread_id, actor=interaction.user),
            )
            await _safe_ephemeral(interaction, "⚠️ This onboarding session is no longer active.")
            return

        questions_for_thread = await self.get_or_load_questions(thread_id, session=session)
        if not questions_for_thread:
            await logs.send_welcome_log(
                "warning",
                view="modal",
                result="questions_missing",
                index=index,
                **self._log_fields(thread_id, actor=interaction.user),
            )
            await _safe_ephemeral(
                interaction,
                "⚠️ Something blinked. Tap **Open questions** again to continue.",
            )
            await self.prompt_retry(interaction, thread_id)
            return

        if not session.visibility:
            try:
                session.visibility = rules.evaluate_visibility(
                    questions_for_thread,
                    session.answers,
                )
            except Exception:
                session.visibility = {}

        gate_context: dict[str, Any] = {
            "view": "modal",
            "view_tag": panels.WELCOME_PANEL_TAG,
            "custom_id": panels.OPEN_QUESTIONS_CUSTOM_ID,
            "view_id": panels.OPEN_QUESTIONS_CUSTOM_ID,
            "step_index": index,
            "flow": self.flow,
        }
        gate_context.setdefault("diag", f"{self.flow}_flow")
        schema_id = getattr(session, "schema_hash", None)
        if schema_id is not None:
            try:
                gate_context["schema_id"] = int(schema_id)
            except (TypeError, ValueError):
                gate_context["schema_id"] = schema_id

        allowed, _ = await self.check_interaction(
            thread_id,
            interaction,
            context=gate_context,
        )
        if not allowed:
            return

        modals_before = build_modals(
            questions_for_thread,
            session.visibility,
            session.answers,
            title_prefix=self._modal_title_prefix(),
        )
        total_before = len(modals_before)

        if total_before and index >= total_before:
            store.set_pending_step(thread_id, {"kind": "inline", "index": 0})
            await logs.send_welcome_log(
                "debug",
                view="modal",
                result="oob_reset",
                index=index,
                **self._log_fields(thread_id, actor=interaction.user),
            )
            await _safe_ephemeral(
                interaction,
                "⚠️ Let’s restart that section. Tap **Open questions** again in the thread.",
            )
            await self.prompt_retry(interaction, thread_id)
            return

        for question in questions:
            raw_value = values.get(question.qid, "")
            state = _visible_state(session.visibility, question.qid)
            required = bool(question.required) and state != "optional"
            answer = raw_value.strip()
            if required and not answer:
                await _safe_ephemeral(
                    interaction,
                    f"⚠️ **{question.label}** is required.",
                )
                return

            meta = self._question_meta(question)

            if not answer:
                await self.set_answer(thread_id, question.qid, None)
                continue

            ok, cleaned, err = self.validate_answer(meta, answer)
            if not ok:
                await self._send_validation_error(interaction, thread_id, meta, err)
                return

            if diag.is_enabled():
                await diag.log_event(
                    "info",
                    "welcome_validator_branch",
                    qid=meta.get("qid"),
                    have_regex=self._has_sheet_regex(meta),
                    type=meta.get("type"),
                )

            await self.set_answer(thread_id, question.qid, cleaned)

        session.visibility = rules.evaluate_visibility(
            questions_for_thread,
            session.answers,
        )

        modals_after = build_modals(
            questions_for_thread,
            session.visibility,
            session.answers,
            title_prefix=self._modal_title_prefix(),
        )
        total_after = len(modals_after)

        await logs.send_welcome_log(
            "debug",
            view="modal",
            result="saved",
            index=index,
            **self._log_fields(thread_id, actor=interaction.user),
        )

        retry_registry = getattr(self, "retry_message_ids", None)
        if isinstance(retry_registry, dict):
            retry_message_id = retry_registry.pop(thread_id, None)
            if retry_message_id:
                try:
                    message = await thread.fetch_message(retry_message_id)
                    await message.delete()
                except Exception:  # pragma: no cover - best-effort cleanup
                    pass

        display_name = _display_name(getattr(interaction, "user", None))
        channel_obj: discord.abc.GuildChannel | discord.Thread | None
        channel_obj = interaction.channel if isinstance(interaction.channel, (discord.Thread, discord.abc.GuildChannel)) else thread
        log.info(
            "✅ Welcome — modal_submit_ok • user=%s • channel=%s",
            display_name,
            _channel_path(channel_obj),
        )

        next_index = index + 1 if index + 1 < total_after else None
        if next_index is None:
            store.set_pending_step(thread_id, None)
            await _safe_ephemeral(
                interaction,
                "✅ Saved! You’re all set for this section.",
            )
            await self.finish_onboarding(
                interaction,
                thread_id,
                session=session,
                thread=thread,
            )
            return

        store.set_pending_step(thread_id, {"kind": "inline", "index": next_index})
        await _safe_ephemeral(
            interaction,
            "✅ Saved! Look for the next prompt in the thread.",
        )
        await self.prompt_next(interaction, thread_id, next_index)

    async def _handle_select_change(
        self,
        thread_id: int,
        interaction: discord.Interaction,
        question: Question,
        values: list[str],
    ) -> None:
        session = store.get(thread_id)
        thread = self._threads.get(thread_id)
        if session is None or thread is None:
            await logs.send_welcome_log(
                "warn",
                view="select",
                result="inactive",
                question=question.qid,
                **self._log_fields(thread_id, actor=interaction.user),
            )
            await _safe_ephemeral(interaction, "⚠️ This onboarding session expired.")
            return

        self._store_select_answer(session, question, values)
        session.visibility = rules.evaluate_visibility(
            self._questions[thread_id],
            session.answers,
        )
        store.set_pending_step(thread_id, session.pending_step)

        async def gate(interaction: discord.Interaction) -> bool:
            allowed, _ = await self.check_interaction(thread_id, interaction)
            return allowed

        pending = session.pending_step or {}
        page = int(pending.get("page", 0))
        view = build_select_view(
            self._questions[thread_id],
            session.visibility,
            session.answers,
            interaction_check=gate,
            page=page,
        )
        if view is None:
            store.set_pending_step(thread_id, None)
            await interaction.response.edit_message(view=None)
            await logs.send_welcome_log(
                "debug",
                view="select",
                result="completed",
                question=question.qid,
                **self._log_fields(thread_id, actor=interaction.user),
            )
            await self._show_preview(thread, session)
            return

        view.on_change = self._select_changed(thread_id)
        view.on_complete = self._select_completed(thread_id)
        view.on_page_change = self._select_page_updated(thread_id)
        store.set_pending_step(thread_id, {"kind": "select", "index": 0, "page": view.page})
        await interaction.response.edit_message(view=view)
        await logs.send_welcome_log(
            "debug",
            view="select",
            result="changed",
            question=question.qid,
            **self._log_fields(thread_id, actor=interaction.user),
        )

    async def _handle_select_complete(
        self,
        thread_id: int,
        interaction: discord.Interaction,
    ) -> None:
        session = store.get(thread_id)
        thread = self._threads.get(thread_id)
        if session is None or thread is None:
            await logs.send_welcome_log(
                "warn",
                view="select",
                result="inactive",
                **self._log_fields(thread_id, actor=interaction.user),
            )
            await _safe_ephemeral(interaction, "⚠️ This onboarding session expired.")
            return

        missing = _missing_required_selects(
            self._questions[thread_id],
            session.visibility,
            session.answers,
        )
        if missing:
            labels = ", ".join(f"**{label}**" for label in missing)
            await _safe_ephemeral(
                interaction,
                f"⚠️ Please choose at least one option for {labels}.",
            )
            return

        store.set_pending_step(thread_id, None)
        await interaction.response.edit_message(view=None)
        await logs.send_welcome_log(
            "info",
            view="select",
            result="submitted",
            **self._log_fields(thread_id, actor=interaction.user),
        )
        await self._show_preview(thread, session)

    def _select_page_updated(self, thread_id: int) -> Callable[[discord.Interaction, int], Awaitable[None]]:
        async def handler(interaction: discord.Interaction, page: int) -> None:
            allowed, _ = await self.check_interaction(thread_id, interaction)
            if not allowed:
                return
            session = store.get(thread_id)
            if session is None:
                return
            pending = dict(session.pending_step or {"kind": "select", "index": 0})
            pending["page"] = page
            store.set_pending_step(thread_id, pending)

        return handler

    async def _show_preview(
        self,
        thread: discord.Thread,
        session: SessionData,
    ) -> None:
        thread_id = int(thread.id)
        embed = self._build_preview_embed(thread_id, session)
        view = _PreviewView(self, thread_id)
        message = self._preview_messages.get(thread_id)
        if message:
            await message.edit(embed=embed, view=view)
        else:
            message = await thread.send(embed=embed, view=view)
            self._preview_messages[thread_id] = message
        store.set_preview_message(
            thread_id,
            message_id=message.id,
            channel_id=getattr(message.channel, "id", None),
        )
        store.set_pending_step(thread_id, None)
        if thread_id not in self._preview_logged:
            self._preview_logged.add(thread_id)
            await logs.send_welcome_log(
                "debug",
                view="preview",
                result="rendered",
                source=self._sources.get(thread_id, "unknown"),
                schema=session.schema_hash,
                **self._log_fields(thread_id),
            )

    def _build_preview_embed(self, thread_id: int, session: SessionData) -> discord.Embed:
        embed = discord.Embed(title="Review your responses")
        embed.description = "Confirm the information below before submitting."

        for question in self._questions.get(thread_id, []):
            state = _visible_state(session.visibility, question.qid)
            if state == "skip":
                continue
            value = _preview_value_for_question(question, session.answers.get(question.qid))
            if not value:
                value = "*(skipped)*"
            embed.add_field(name=question.label, value=value, inline=False)
        return embed

    async def _handle_confirm(
        self,
        thread_id: int,
        interaction: discord.Interaction,
    ) -> None:
        session = store.get(thread_id)
        thread = self._threads.get(thread_id)
        if session is None or thread is None:
            await logs.send_welcome_log(
                "warn",
                view="preview",
                result="inactive",
                **self._log_fields(thread_id, actor=interaction.user),
            )
            await _safe_ephemeral(interaction, "⚠️ This onboarding session expired.")
            return

        await interaction.response.edit_message(view=None)

        preview_message = self._preview_messages.pop(thread_id, None)
        if preview_message is not None:
            try:
                await preview_message.delete()
            except Exception:
                try:
                    await preview_message.edit(view=None)
                except Exception:
                    log.warning("failed to remove preview after confirmation", exc_info=True)

        summary_author = self._resolve_summary_author(thread, interaction)
        summary_embed = build_summary_embed(
            self.flow,
            session.answers,
            summary_author,
            session.schema_hash or "",
            session.visibility,
        )

        await thread.send(embed=summary_embed)
        await thread.send("@RecruitmentCoordinator")

        await logs.send_welcome_log(
            "info",
            result="completed",
            view="preview",
            source=self._sources.get(thread_id, "unknown"),
            schema=session.schema_hash,
            details=_final_fields(self._questions[thread_id], session.answers),
            **self._log_fields(thread_id, actor=interaction.user),
        )

        store.set_preview_message(thread_id, message_id=None, channel_id=None)
        self._cleanup_session(thread_id)

    async def _handle_edit(
        self,
        thread_id: int,
        interaction: discord.Interaction,
    ) -> None:
        session = store.get(thread_id)
        thread = self._threads.get(thread_id)
        if session is None or thread is None:
            await logs.send_welcome_log(
                "warn",
                view="preview",
                result="inactive",
                **self._log_fields(thread_id, actor=interaction.user),
            )
            await _safe_ephemeral(interaction, "⚠️ This onboarding session expired.")
            return

        await interaction.response.edit_message(view=None)
        await _safe_followup(
            interaction,
            "🛠️ Re-opening the form so you can make changes.",
        )
        await logs.send_welcome_log(
            "info",
            view="preview",
            result="reopened",
            **self._log_fields(thread_id, actor=interaction.user),
        )
        anchor = getattr(interaction, "message", None)
        await self._start_modal_step(thread, session, anchor=anchor)

    def _cleanup_session(self, thread_id: int) -> None:
        store.end(thread_id)
        self._threads.pop(thread_id, None)
        self._questions.pop(thread_id, None)
        self.answers_by_thread.pop(thread_id, None)
        self._select_messages.pop(thread_id, None)
        self._preview_messages.pop(thread_id, None)
        self._sources.pop(thread_id, None)
        self._allowed_users.pop(thread_id, None)
        self._target_users.pop(thread_id, None)
        self._target_message_ids.pop(thread_id, None)
        self._preview_logged.discard(thread_id)
        panel_message_id = self._panel_messages.pop(thread_id, None)
        if panel_message_id is not None:
            panels.mark_panel_inactive_by_message(panel_message_id)
        self._prefetched_panels.pop(thread_id, None)
        panels.unbind_controller(thread_id)

    async def _ensure_target_cached(
        self, thread_id: int, *, refresh_if_none: bool = False
    ) -> None:
        cached = self._target_users.get(thread_id, ...)
        if cached is not ...:
            if not (cached is None and refresh_if_none):
                return

        thread = self._threads.get(thread_id)
        if thread is None:
            self._target_users[thread_id] = None
            return

        target_id: int | None = None
        message_id: int | None = None

        message = await locate_welcome_message(thread)
        target_id, message_id = extract_target_from_message(message)

        self._target_users[thread_id] = target_id
        if message_id is not None:
            self._target_message_ids[thread_id] = message_id

    @staticmethod
    def _member_role_ids(member: discord.abc.User | discord.Member | None) -> set[int]:
        if not isinstance(member, discord.Member):
            return set()
        role_ids: set[int] = set()
        for role in getattr(member, "roles", []) or []:
            role_id = getattr(role, "id", None)
            if role_id is None:
                continue
            try:
                role_ids.add(int(role_id))
            except (TypeError, ValueError):
                continue
        return role_ids

    async def _log_access(
        self,
        level: str,
        result: str,
        thread_id: int,
        interaction: discord.Interaction,
        context: dict[str, Any],
        **extra: Any,
    ) -> None:
        payload = self._log_fields(thread_id, actor=interaction.user)
        payload.update(context)
        payload["result"] = result
        if extra:
            payload.update(extra)
        await logs.send_welcome_log(level, **payload)

    async def check_interaction(
        self,
        thread_id: int,
        interaction: discord.Interaction,
        *,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, str | None]:
        allowed_cache = self._allowed_users.setdefault(thread_id, set())
        actor = interaction.user
        actor_id = getattr(actor, "id", None)

        log_context: dict[str, Any] | None = None
        if context is not None:
            log_context = dict(context)
            if actor_id is not None:
                log_context.setdefault("actor_id", int(actor_id))
            target_message_id = self._target_message_ids.get(thread_id)
            if target_message_id is not None:
                log_context.setdefault("target_message_id", int(target_message_id))
            thread = self._thread_for(thread_id)
            parent_id = getattr(thread, "parent_id", None)
            if parent_id is not None:
                log_context.setdefault("parent_channel_id", int(parent_id))
        target_id = self._target_users.get(thread_id)
        if target_id is not None and log_context is not None:
            log_context.setdefault("target_user_id", int(target_id))

        if actor_id is not None and actor_id in allowed_cache:
            fallback_thread = interaction.channel if isinstance(interaction.channel, discord.Thread) else self._thread_for(thread_id)
            _log_gate(interaction, allowed=True, reason="cached", fallback_thread=fallback_thread)
            if log_context is not None:
                await self._log_access("info", "allowed", thread_id, interaction, log_context)
            return True, None

        thread = self._thread_for(thread_id)
        subject = interaction.channel if isinstance(interaction.channel, discord.Thread) else None

        if subject is None:
            _log_gate(interaction, allowed=False, reason="no_thread", fallback_thread=thread)
            if log_context is not None:
                await self._log_access("warn", "denied_scope", thread_id, interaction, log_context)
            await _safe_ephemeral(
                interaction,
                "⚠️ This onboarding panel only works inside ticket threads.",
            )
            return False, "no_thread"

        perms = subject.permissions_for(cast(discord.abc.Snowflake, actor))
        if not perms.view_channel:
            _log_gate(interaction, allowed=False, reason="no_view_channel", fallback_thread=subject)
            if log_context is not None:
                await self._log_access(
                    "warn",
                    "denied_permission",
                    thread_id,
                    interaction,
                    log_context,
                    reason="no_view_channel",
                )
            await _safe_ephemeral(
                interaction,
                "⚠️ You need view access to this thread before starting the onboarding form.",
            )
            return False, "no_view_channel"

        if actor_id is not None:
            allowed_cache.add(int(actor_id))
        if log_context is not None:
            await self._log_access("info", "allowed", thread_id, interaction, log_context)
        _log_gate(interaction, allowed=True, reason="view_channel", fallback_thread=subject)
        return True, None

    def _store_select_answer(
        self,
        session: SessionData,
        question: Question,
        values: Iterable[str],
    ) -> None:
        options = {option.value: option for option in question.options}
        if question.type == "single-select":
            if values:
                value = next(iter(values))
                option = options.get(value)
                if option:
                    session.answers[question.qid] = {
                        "value": option.value,
                        "label": option.label,
                    }
                else:
                    session.answers.pop(question.qid, None)
            else:
                session.answers.pop(question.qid, None)
            return

        selected: list[dict[str, str]] = []
        for token in values:
            option = options.get(token)
            if option:
                selected.append({"value": option.value, "label": option.label})
        if selected:
            session.answers[question.qid] = selected
        else:
            session.answers.pop(question.qid, None)

    def _modal_title_prefix(self) -> str:
        return "Onboarding questions"

    def _modal_intro_text(self) -> str:
        return "🧭 Let's capture some details. Press the button below to start."

    def _select_intro_text(self) -> str:
        return "🔽 Choose the options that apply using the menus below."

    def _resolve_summary_author(
        self, thread: discord.Thread, interaction: discord.Interaction
    ) -> discord.Member:
        owner = getattr(thread, "owner", None)
        if isinstance(owner, discord.Member):
            return owner

        guild = thread.guild
        owner_id = getattr(thread, "owner_id", None)
        if guild and owner_id:
            member = guild.get_member(owner_id)
            if member is not None:
                return member

        user = interaction.user
        if isinstance(user, discord.Member):
            return user

        if guild is not None and getattr(user, "id", None):
            member = guild.get_member(int(user.id))
            if member is not None:
                return member

        if guild is not None:
            me = guild.me
            if me is not None:
                return me

        user_obj = interaction.user
        if isinstance(user_obj, discord.User):
            return cast(discord.Member, user_obj)

        raise TypeError("Unable to resolve summary author for onboarding thread")


class WelcomeController(BaseWelcomeController):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot, flow="welcome")


class _PreviewView(discord.ui.View):
    def __init__(self, controller: BaseWelcomeController, thread_id: int) -> None:
        super().__init__(timeout=600)
        self.controller = controller
        self.thread_id = thread_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:  # pragma: no cover - network
        allowed, _ = await self.controller.check_interaction(self.thread_id, interaction)
        return allowed

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, custom_id="ob.confirm")
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:  # pragma: no cover - network
        if getattr(interaction, "_c1c_claimed", False):
            return
        setattr(interaction, "_c1c_claimed", True)
        thread = interaction.channel if isinstance(interaction.channel, discord.Thread) else None
        context = {
            **logs.thread_context(thread if isinstance(thread, discord.Thread) else None),
            "actor": logs.format_actor(interaction.user),
            "view": "preview",
            "view_id": "ob.confirm",
        }
        actor_name = logs.format_actor_handle(interaction.user)
        if actor_name:
            context["actor_name"] = actor_name
        await logs.send_welcome_log("debug", result="clicked", **context)
        await self.controller._handle_confirm(self.thread_id, interaction)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary, custom_id="ob.edit")
    async def edit(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:  # pragma: no cover - network
        if getattr(interaction, "_c1c_claimed", False):
            return
        setattr(interaction, "_c1c_claimed", True)
        thread = interaction.channel if isinstance(interaction.channel, discord.Thread) else None
        context = {
            **logs.thread_context(thread if isinstance(thread, discord.Thread) else None),
            "actor": logs.format_actor(interaction.user),
            "view": "preview",
            "view_id": "ob.edit",
        }
        actor_name = logs.format_actor_handle(interaction.user)
        if actor_name:
            context["actor_name"] = actor_name
        await logs.send_welcome_log("debug", result="clicked", **context)
        await self.controller._handle_edit(self.thread_id, interaction)

    async def on_timeout(self) -> None:  # pragma: no cover - network
        for child in self.children:
            child.disabled = True


async def _safe_ephemeral(interaction: discord.Interaction, message: str) -> None:
    diag_state = diag.interaction_state(interaction)
    response_done = False
    try:
        response_done = bool(interaction.response.is_done())
    except Exception:  # pragma: no cover - defensive guard
        response_done = False
    deny_path = "followup" if response_done else "initial_response"
    diag_state["deny_path"] = deny_path
    diag_state["response_is_done"] = response_done
    if diag.is_enabled():
        await diag.log_event("info", "deny_notice_pre", **diag_state)
    try:
        if response_done:
            await _edit_deferred_response(interaction, message)
        else:
            await interaction.response.send_message(message, ephemeral=True)
        if diag.is_enabled():
            await diag.log_event("info", "deny_notice_sent", **diag_state)
    except Exception:  # pragma: no cover - defensive network handling
        if diag.is_enabled():
            error_type = None
            status = None
            code = None
            if isinstance(exc := sys.exc_info()[1], discord.Forbidden):
                error_type = "Forbidden"
                status = getattr(exc, "status", None)
                code = getattr(exc, "code", None)
            elif isinstance(exc, discord.HTTPException):
                error_type = "HTTPException"
                status = getattr(exc, "status", None)
                code = getattr(exc, "code", None)
            else:
                error_type = exc.__class__.__name__ if exc else None
            await diag.log_event(
                "error",
                "deny_notice_error",
                error_type=error_type,
                status=status,
                code=code,
                **diag_state,
            )
        log.warning("failed to send denial response", exc_info=True)


def _visible_state(visibility: dict[str, dict[str, str]], qid: str) -> str:
    return visibility.get(qid, {}).get("state", "show")


def _preview_value_for_question(question: Question, stored: Any) -> str:
    if stored is None:
        return ""
    if question.type in TEXT_TYPES:
        return str(stored)
    if question.type == "single-select":
        if isinstance(stored, dict):
            label = stored.get("label") or stored.get("value")
            return str(label or "")
        return str(stored)
    if isinstance(stored, Iterable):
        labels = []
        for item in stored:
            if isinstance(item, dict):
                label = item.get("label") or item.get("value")
                if label:
                    labels.append(str(label))
            else:
                labels.append(str(item))
        return ", ".join(labels)
    return str(stored)


def _missing_required_selects(
    questions: Sequence[Question],
    visibility: dict[str, dict[str, str]],
    answers: dict[str, Any],
) -> list[str]:
    missing: list[str] = []
    for question in questions:
        if question.type not in SELECT_TYPES:
            continue
        state = _visible_state(visibility, question.qid)
        if state == "skip":
            continue
        required = bool(question.required) and state != "optional"
        if not required:
            continue
        value = answers.get(question.qid)
        if not _has_select_answer(value):
            missing.append(question.label)
    return missing


def _has_select_answer(value: Any) -> bool:
    if not value:
        return False
    if isinstance(value, dict):
        if value.get("value"):
            return True
        nested = value.get("values")
        if isinstance(nested, Iterable):
            return any(_has_select_answer(item) for item in nested)
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Iterable):
        return any(_has_select_answer(item) for item in value)
    return bool(value)


def _final_fields(questions: Sequence[Question], answers: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    option_lookup: dict[str, dict[str, str]] = {}
    for question in questions:
        if question.type in SELECT_TYPES:
            option_lookup[question.qid] = {option.value: option.label for option in question.options}
    for qid, value in answers.items():
        label_value = _convert_to_labels(value, option_lookup.get(qid, {}))
        if isinstance(label_value, str) and len(label_value) > 300:
            label_value = label_value[:297] + "..."
        fields[qid] = label_value
    return fields


def _convert_to_labels(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, dict):
        if "value" in value:
            token = value.get("value")
            return mapping.get(token, str(value.get("label") or token))
        if "values" in value:
            items = value.get("values")
            if isinstance(items, Iterable):
                return [
                    mapping.get(item.get("value"), item.get("label"))
                    if isinstance(item, dict)
                    else mapping.get(str(item), str(item))
                    for item in items
                ]
        return {key: _convert_to_labels(val, mapping) for key, val in value.items()}
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return [_convert_to_labels(item, mapping) for item in value]
    if isinstance(value, str):
        return mapping.get(value, value)
    return value


def _safe_followup(interaction: discord.Interaction, message: str) -> Awaitable[None]:
    async def runner() -> None:
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception:
            log.warning("failed to send follow-up", exc_info=True)

    return runner()


__all__ = ["WelcomeController", "BaseWelcomeController"]
