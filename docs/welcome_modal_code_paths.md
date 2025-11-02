# Welcome Modal — Code Path Audit (Full Source Context)

## A. Button Handler → Modal Call (with order of awaits)

### modules/onboarding/ui/panels.py:244-405
```python
@discord.ui.button(
    label="Open questions",
    style=discord.ButtonStyle.primary,
    custom_id=OPEN_QUESTIONS_CUSTOM_ID,
)
async def launch(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
    try:
        await self._handle_launch(interaction)  # [AWAIT_BEFORE_MODAL]
    except Exception:
        await self._ensure_error_notice(interaction)  # [SEND_BEFORE_MODAL]
        raise

async def _handle_launch(self, interaction: discord.Interaction) -> None:
    state = diag.interaction_state(interaction)
    controller = self._controller
    thread_id = state.get("thread_id")
    target_user_id: int | None = None
    if controller is not None and thread_id is not None:
        getter = getattr(controller, "diag_target_user_id", None)
        if callable(getter):
            target_user_id = getter(int(thread_id))
    if diag.is_enabled():
        await diag.log_event(  # [AWAIT_BEFORE_MODAL]
            "info",
            "panel_button_clicked",
            custom_id=OPEN_QUESTIONS_CUSTOM_ID,
            target_user_id=target_user_id,
            ambiguous_target=target_user_id is None,
            **state,
        )

    if not _claim_interaction(interaction):
        return

    channel = getattr(interaction, "channel", None)
    thread = channel if isinstance(channel, discord.Thread) else None
    controller, thread_id = self._resolve(interaction)
    message = getattr(interaction, "message", None)
    message_id = getattr(message, "id", None)
    actor_id = getattr(interaction.user, "id", None)

    snapshot, permissions_text, _missing = diag.permission_snapshot(interaction)

    controller_context: dict[str, Any] = {
        "view": "panel",
        "view_tag": WELCOME_PANEL_TAG,
        "custom_id": OPEN_QUESTIONS_CUSTOM_ID,
        "view_id": OPEN_QUESTIONS_CUSTOM_ID,
        "app_permissions": permissions_text,
        "app_perms_text": permissions_text,
        "app_permissions_snapshot": snapshot,
    }
    if thread_id is not None:
        try:
            controller_context["thread_id"] = int(thread_id)
        except (TypeError, ValueError):
            pass
    if message_id is not None:
        try:
            controller_context["message_id"] = int(message_id)
        except (TypeError, ValueError):
            pass
    if actor_id is not None:
        try:
            controller_context["actor_id"] = int(actor_id)
        except (TypeError, ValueError):
            pass
    if isinstance(thread, discord.Thread):
        parent_id = getattr(thread, "parent_id", None)
        if parent_id is not None:
            try:
                controller_context["parent_channel_id"] = int(parent_id)
            except (TypeError, ValueError):
                pass
    else:
        parent_id = None

    log_context: dict[str, Any] = {
        **logs.thread_context(thread),
        "view": "panel",
        "view_tag": WELCOME_PANEL_TAG,
        "custom_id": OPEN_QUESTIONS_CUSTOM_ID,
        "view_id": OPEN_QUESTIONS_CUSTOM_ID,
        "actor": logs.format_actor(interaction.user),
        "app_permissions": permissions_text,
        "app_perms_text": permissions_text,
        "app_permissions_snapshot": snapshot,
    }
    actor_name = logs.format_actor_handle(interaction.user)
    if actor_name:
        log_context["actor_name"] = actor_name
    if thread_id is not None and "thread" not in log_context:
        log_context["thread"] = logs.format_thread(thread_id)
    if thread_id is not None:
        try:
            log_context["thread_id"] = int(thread_id)
        except (TypeError, ValueError):
            pass
    if message_id is not None:
        try:
            log_context["message_id"] = int(message_id)
        except (TypeError, ValueError):
            pass
    if actor_id is not None:
        try:
            log_context["actor_id"] = int(actor_id)
        except (TypeError, ValueError):
            pass
    if parent_id is not None:
        try:
            log_context["parent_channel_id"] = int(parent_id)
        except (TypeError, ValueError):
            pass

    flow_name = getattr(controller, "flow", None) if controller is not None else None
    if flow_name:
        log_context["flow"] = flow_name
        log_context.setdefault("diag", f"{flow_name}_flow")
    else:
        log_context.setdefault("diag", "welcome_flow")

    button_log_context = dict(log_context)
    button_log_context.setdefault("event", "panel_button_clicked")
    button_log_context.setdefault("result", "clicked")
    button_log_context.setdefault("view_tag", WELCOME_PANEL_TAG)

    if controller is None or thread_id is None:
        await self._restart_from_view(interaction, log_context)  # [AWAIT_BEFORE_MODAL]
        return

    actor = interaction.user
    actor_id = getattr(actor, "id", None)

    try:
        await controller._handle_modal_launch(  # [AWAIT_BEFORE_MODAL]
            thread_id,
            interaction,
            context=controller_context,
        )
    except Exception as exc:
        error_context = dict(log_context)
        await logs.send_welcome_exception("error", exc, **error_context)  # [AWAIT_BEFORE_MODAL]
        await self._ensure_error_notice(interaction)  # [SEND_BEFORE_MODAL]
        raise
    finally:
        try:
            await logs.send_welcome_log("info", **button_log_context)  # [AWAIT_BEFORE_MODAL]
        except Exception:
            log.warning("failed to emit welcome panel button log", exc_info=True)  # [TRY_SWALLOW]
```

### modules/onboarding/controllers/welcome_controller.py:423-606
```python
async def _start_select_step(self, thread: discord.Thread, session: SessionData) -> None:
    thread_id = int(thread.id)

    async def gate(interaction: discord.Interaction) -> bool:
        allowed, _ = await self.check_interaction(thread_id, interaction)  # [AWAIT_BEFORE_MODAL]
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
        await self._show_preview(thread, session)  # [AWAIT_BEFORE_MODAL]
        return

    view.on_change = self._select_changed(thread_id)
    view.on_complete = self._select_completed(thread_id)
    view.on_page_change = self._select_page_updated(thread_id)
    store.set_pending_step(thread_id, {"kind": "select", "index": 0, "page": view.page})
    content = self._select_intro_text()
    message = self._select_messages.get(thread_id)
    if message:
        await message.edit(content=content, view=view)  # [SEND_BEFORE_MODAL]
    else:
        message = await thread.send(content, view=view)  # [SEND_BEFORE_MODAL]
        self._select_messages[thread_id] = message
    await logs.send_welcome_log(  # [AWAIT_BEFORE_MODAL]
        "debug",
        view="select",
        result="ready",
        **self._log_fields(thread_id),
    )

async def _handle_modal_launch(
    self,
    thread_id: int,
    interaction: discord.Interaction,
    *,
    context: dict[str, Any] | None = None,
) -> None:
    session = store.get(thread_id)
    thread = self._threads.get(thread_id)
    if session is None or thread is None:
        await self._restart_from_interaction(thread_id, interaction, context=context)  # [AWAIT_BEFORE_MODAL]
        return

    diag_state = diag.interaction_state(interaction)
    diag_state["thread_id"] = thread_id
    target_user_id = self._target_users.get(thread_id)
    diag_state["target_user_id"] = target_user_id
    diag_state["ambiguous_target"] = target_user_id is None
    diag_state["custom_id"] = panels.OPEN_QUESTIONS_CUSTOM_ID

    diag_enabled = diag.is_enabled()
    if diag_state.get("response_is_done"):
        if diag_enabled:
            await diag.log_event(  # [AWAIT_BEFORE_MODAL]
                "info",
                "modal_launch_skipped",
                skip_reason="response_done",
                **diag_state,
            )
        return

    modals = build_modals(
        self._questions[thread_id],
        session.visibility,
        session.answers,
        title_prefix=self._modal_title_prefix(),
    )
    pending = session.pending_step or {}
    index = int(pending.get("index", 0))
    if index >= len(modals):
        store.set_pending_step(thread_id, None)
        await _safe_ephemeral(interaction, "No more questions on this step.")  # [SEND_BEFORE_MODAL]
        await self._start_select_step(thread, session)  # [AWAIT_BEFORE_MODAL]
        return

    questions_for_step = list(modals[index].questions)
    modal = WelcomeQuestionnaireModal(
        questions=questions_for_step,
        step_index=index,
        total_steps=len(modals),
        title_prefix=self._modal_title_prefix(),
        answers=session.answers,
        visibility=session.visibility,
        on_submit=self._modal_submitted(thread_id, questions_for_step, index),
    )
    store.set_pending_step(thread_id, {"kind": "modal", "index": index})
    diag_state["modal_index"] = index
    diag_state["schema_id"] = session.schema_hash
    diag_state["about_to_send_modal"] = True
    diag_tasks: list[Awaitable[None]] = []
    if diag_enabled:
        diag_tasks.append(diag.log_event("info", "modal_launch_pre", **diag_state))
        if diag_state.get("response_is_done"):
            diag_tasks.append(
                diag.log_event(
                    "info",
                    "modal_launch_followup",
                    followup_path=True,
                    **diag_state,
                )
            )
    display_name = _display_name(getattr(interaction, "user", None))
    channel_obj: discord.abc.GuildChannel | discord.Thread | None
    channel_obj = interaction.channel if isinstance(interaction.channel, (discord.Thread, discord.abc.GuildChannel)) else thread
    channel_label = _channel_path(channel_obj)
    log.info(
        "✅ Welcome — modal_open • user=%s • channel=%s",
        display_name,
        channel_label,
    )
    try:
        await interaction.response.send_modal(modal)
    except discord.InteractionResponded:
        log.warning(
            "⚠️ Welcome — modal_already_responded • user=%s • channel=%s",
            display_name,
            channel_label,
        )
        if diag_enabled:
            diag_tasks.append(
                diag.log_event(
                    "warning",
                    "modal_launch_skipped",
                    skip_reason="interaction_already_responded",
                    **diag_state,
                )
            )
            await asyncio.gather(*diag_tasks, return_exceptions=True)
        return
    except Exception as exc:
        if diag_enabled:
            diag_tasks.append(
                diag.log_event(
                    "error",
                    "modal_launch_error",
                    exception_type=exc.__class__.__name__,
                    exception_message=str(exc),
                    **diag_state,
                )
            )
            await asyncio.gather(*diag_tasks, return_exceptions=True)
        raise
    else:
        if diag_enabled:
            diag_tasks.append(
                diag.log_event("info", "modal_launch_sent", modal_sent=True, **diag_state)
            )
            await asyncio.gather(*diag_tasks, return_exceptions=True)
    await logs.send_welcome_log(
        "debug",
        view="modal",
        result="launched",
        index=index,
        **self._log_fields(thread_id, actor=interaction.user),
    )
```

## B. Helpers that might respond before the modal

### modules/onboarding/controllers/welcome_controller.py:82-94, 1336-1370
```python
async def _edit_deferred_response(interaction: discord.Interaction, message: str) -> None:
    try:
        await interaction.edit_original_response(content=message)  # [SEND_BEFORE_MODAL]
    except Exception as exc:  # [TRY_SWALLOW]
        _log_followup_fallback(interaction, action="edit_original", error=exc)
        followup = getattr(interaction, "followup", None)
        if followup is None:
            log.debug("followup handler missing; skipping deferred notice")
            return
        try:
            await followup.send(message, ephemeral=True)  # [SEND_BEFORE_MODAL]
        except Exception:  # [TRY_SWALLOW]
            log.warning("failed to deliver followup message", exc_info=True)

async def _safe_ephemeral(interaction: discord.Interaction, message: str) -> None:
    diag_state = diag.interaction_state(interaction)
    response_done = False
    try:
        response_done = bool(interaction.response.is_done())
    except Exception:  # [TRY_SWALLOW]
        response_done = False
    deny_path = "followup" if response_done else "initial_response"
    diag_state["deny_path"] = deny_path
    diag_state["response_is_done"] = response_done
    if diag.is_enabled():
        await diag.log_event("info", "deny_notice_pre", **diag_state)  # [AWAIT_BEFORE_MODAL]
    try:
        if response_done:
            await _edit_deferred_response(interaction, message)  # [SEND_BEFORE_MODAL]
        else:
            await interaction.response.send_message(message, ephemeral=True)  # [SEND_BEFORE_MODAL]
        if diag.is_enabled():
            await diag.log_event("info", "deny_notice_sent", **diag_state)  # [AWAIT_BEFORE_MODAL]
    except Exception:  # [TRY_SWALLOW]
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
                "warning",
                "deny_notice_failed",
                error_type=error_type,
                status=status,
                code=code,
                **diag_state,
            )
```

### modules/onboarding/controllers/welcome_controller.py:423-454
```python
async def _start_select_step(self, thread: discord.Thread, session: SessionData) -> None:
    ...
    message = self._select_messages.get(thread_id)
    if message:
        await message.edit(content=content, view=view)  # [SEND_BEFORE_MODAL]
    else:
        message = await thread.send(content, view=view)  # [SEND_BEFORE_MODAL]
        self._select_messages[thread_id] = message
```

### modules/onboarding/ui/panels.py:496-602
```python
async def _ensure_error_notice(self, interaction: discord.Interaction) -> None:
    identifier = getattr(interaction, "id", None)
    if identifier is None:
        identifier = id(interaction)
    try:
        key = int(identifier)
    except (TypeError, ValueError):
        key = id(interaction)
    if key in self._error_notice_ids:
        return
    self._error_notice_ids.add(key)
    if interaction.response.is_done():
        await _edit_original_response(interaction, content=self.ERROR_NOTICE)  # [SEND_BEFORE_MODAL]
        return
    try:
        await interaction.response.send_message(self.ERROR_NOTICE, ephemeral=True)  # [SEND_BEFORE_MODAL]
    except Exception:  # [TRY_SWALLOW]
        log.warning("failed to send error notice", exc_info=True)

async def _notify_restart(self, interaction: discord.Interaction) -> None:
    message = "♻️ Restarting the onboarding form…"
    if interaction.response.is_done():
        await _edit_original_response(interaction, content=message)  # [SEND_BEFORE_MODAL]
        return
    try:
        await interaction.response.send_message(message, ephemeral=True)  # [SEND_BEFORE_MODAL]
    except Exception:  # [TRY_SWALLOW]
        log.warning("failed to send restart notice", exc_info=True)
```

### modules/onboarding/ui/panels.py:127-131
```python
def _claim_interaction(interaction: discord.Interaction) -> bool:
    if getattr(interaction, "_c1c_claimed", False):
        return False
    setattr(interaction, "_c1c_claimed", True)
    return True
```

## C. Modal Definition(s)

### modules/onboarding/ui/modal_renderer.py:14-99
```python
class WelcomeQuestionnaireModal(discord.ui.Modal):
    """Modal that renders a slice of onboarding questions."""

    def __init__(
        self,
        *,
        questions: Sequence[Question],
        step_index: int,
        total_steps: int,
        title_prefix: str = "Onboarding",
        answers: dict[str, object] | None = None,
        visibility: dict[str, dict[str, str]] | None = None,
        on_submit: Callable[[discord.Interaction, dict[str, str]], Awaitable[None]] | None = None,
    ) -> None:
        title = f"{title_prefix} ({step_index + 1}/{max(total_steps, 1)})"
        super().__init__(title=title, timeout=600)
        self.questions = list(questions)
        self.step_index = step_index
        self.total_steps = total_steps
        self.answers = answers or {}
        self.visibility = visibility or {}
        self.submit_callback = on_submit

        for question in self.questions:
            default = _coerce_answer_to_default(self.answers.get(question.qid))
            state = _visible_state(self.visibility, question.qid)
            required = bool(question.required) and state != "optional"
            text_input = discord.ui.TextInput(
                label=question.label,
                custom_id=question.qid,
                placeholder=question.help or None,
                style=(
                    discord.TextStyle.long
                    if question.type == "paragraph"
                    else discord.TextStyle.short
                ),
                default=default,
                required=required,
                max_length=question.maxlen or None,
            )
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:  # [AWAIT_BEFORE_MODAL]
        try:
            await interaction.response.defer(ephemeral=True)  # [DEFER_BEFORE_MODAL]
        except discord.InteractionResponded:
            pass
        payload: dict[str, str] = {}
        for child in self.children:
            if isinstance(child, discord.ui.TextInput):
                payload[child.custom_id] = child.value
        if self.submit_callback is not None:
            await self.submit_callback(interaction, payload)  # [AWAIT_BEFORE_MODAL]
```

Notes: Dynamic title prefix keeps the modal title concise; `_chunk(..., 5)` in `build_modals` caps each modal at five text inputs with unique `custom_id` values sourced from sheet `qid`s.

## D. Persistent View Registration

### modules/onboarding/ui/panels.py:169-205
```python
def register_persistent_views(bot: discord.Client) -> None:
    view = OpenQuestionsPanelView()
    registered = False
    duplicate = False
    stacksite: str | None = None
    try:
        bot.add_view(view)
        registered = True
    except Exception:
        log.warning("failed to register persistent welcome panel view", exc_info=True)
    finally:
        if diag.is_enabled():
            key = view.__class__.__name__
            _REGISTRATION_COUNTS[key] = _REGISTRATION_COUNTS.get(key, 0) + 1
            duplicate = _REGISTRATION_COUNTS[key] > 1
            if duplicate:
                stacksite = diag.relative_stack_site(frame_level=2)
            custom_ids = [
                child.custom_id
                for child in view.children
                if isinstance(child, discord.ui.Button) and child.custom_id
            ]
            fields = {
                "view": key,
                "registered": registered,
                "timeout": view.timeout,
                "disable_on_timeout": getattr(view, "disable_on_timeout", None),
                "custom_ids": custom_ids,
            }
            if duplicate:
                fields["duplicate_registration"] = True
                if stacksite:
                    fields["stacksite"] = stacksite
            diag.log_event_sync("info", "persistent_view_registered", **fields)
    if registered:
        log.info("🧭 welcome.view registered (timeout=%s)", view.timeout)
        log.info("✅ Welcome — persistent-view • view=%s", view.__class__.__name__)
```

### modules/common/runtime.py:679-703
```python
async def load_extensions(self) -> None:
    """Load all feature modules into the shared bot instance."""
    ...
    from modules.onboarding.ui import panels as onboarding_panels
    ...
    onboarding_panels.register_persistent_views(self.bot)
```

## E. Double-respond Guards

### modules/onboarding/ui/panels.py:95-101
```python
async def _defer_interaction(interaction: discord.Interaction) -> None:
    try:
        await interaction.response.defer(ephemeral=True)  # [DEFER_BEFORE_MODAL]
    except discord.Forbidden:
        await interaction.response.defer()
    except discord.InteractionResponded:
        return
```

### modules/onboarding/controllers/welcome_controller.py:563-579
```python
try:
    await interaction.response.send_modal(modal)
except discord.InteractionResponded:
    log.warning(
        "⚠️ Welcome — modal_already_responded • user=%s • channel=%s",
        display_name,
        channel_label,
    )
    if diag_enabled:
        diag_tasks.append(
            diag.log_event(
                "warning",
                "modal_launch_skipped",
                skip_reason="interaction_already_responded",
                **diag_state,
            )
        )
        await asyncio.gather(*diag_tasks, return_exceptions=True)
    return
```

### modules/onboarding/ui/modal_renderer.py:56-60
```python
async def on_submit(self, interaction: discord.Interaction) -> None:
    try:
        await interaction.response.defer(ephemeral=True)  # [DEFER_BEFORE_MODAL]
    except discord.InteractionResponded:
        pass
```

## F. Ranked Suspects (from Evidence)

1. **Interaction already marked as responded** — `diag_state["response_is_done"]` short-circuits the modal send whenever earlier logic consumes the interaction, logging `modal_launch_skipped`. (modules/onboarding/controllers/welcome_controller.py:502-511)
2. **Pending step exhaustion** — When the stored step index exceeds available modal pages, `_safe_ephemeral` responds and `_start_select_step` relaunches the selector instead of opening a modal. (modules/onboarding/controllers/welcome_controller.py:519-525)
3. **Duplicate interaction claim** — `_claim_interaction` prevents re-entry if another handler has already set `_c1c_claimed`. (modules/onboarding/ui/panels.py:127-131)
