import discord
from modules.onboarding.ui.components import SingleSelectView, MultiSelectView

GUIDANCE = "Use the controls below. Don’t type answers as messages—those won’t be read."

def _answer_chip(val):
    if not val or val == "—":
        return "—"
    if isinstance(val, (list, tuple)):
        joined = ", ".join(val)
        return joined if len(joined) <= 120 else joined[:120] + "…"
    return str(val)

def _parse_values(q) -> list[str]:
    raw = (q.get("values") or "").strip()
    return [s.strip() for s in raw.split(",") if s.strip()]

def build_view(
    controller,
    session,
    q: dict,
    required: bool,
    has_answer: bool,
    optional: bool,
    *,
    is_last: bool,
):
    values = _parse_values(q)
    ans = session.get_answer(q["gid"])

    title = f"**{q['label']}** {'(required)' if required else '(optional)'}"
    help_line = f"_{q.get('help') or ''}_" if q.get('help') else ""
    chip = f"🎯 Selected: {_answer_chip(ans)}"

    lines = [GUIDANCE, "", title]
    if help_line:
        lines.append(help_line)
    lines += ["", chip, ""]
    content = "\n".join(lines)

    view = discord.ui.View(timeout=180)

    # Input control
    if values:
        if q["type"] == "single-select":
            def on_pick(interaction: discord.Interaction, value: str):
                controller._async_spawn(controller._save_select_answer(interaction, session, q, value))

            sv = SingleSelectView(
                values,
                preselect=str(ans) if isinstance(ans, str) else None,
                on_pick=on_pick,
            )
            view.add_item(sv.select)
        else:
            def on_pick(interaction: discord.Interaction, values_list: list[str]):
                controller._async_spawn(controller._save_multi_answer(interaction, session, q, values_list))

            mv = MultiSelectView(
                values,
                preselect=list(ans) if isinstance(ans, (list, tuple)) else [],
                on_pick=on_pick,
            )
            view.add_item(mv.select)
    else:
        # Disabled state if sheet didn't provide options — do not invent choices
        no_opts_button = discord.ui.Button(
            label="No options available (sheet 'values' empty)",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            custom_id="q_no_opts",
        )
        view.add_item(no_opts_button)

    # Nav
    back_button = discord.ui.Button(
        label="Back",
        style=discord.ButtonStyle.secondary,
        custom_id="nav_back",
    )

    async def back_btn(inter, _btn):
        await inter.response.defer_update()
        await controller.back(inter, session)

    back_button.callback = back_btn  # type: ignore[assignment]
    view.add_item(back_button)

    if optional:
        skip_button = discord.ui.Button(
            label="Skip",
            style=discord.ButtonStyle.secondary,
            custom_id="nav_skip",
        )

        async def skip_btn(inter, _btn):
            await inter.response.defer_update()
            await controller.skip(inter, session, q)

        skip_button.callback = skip_btn  # type: ignore[assignment]
        view.add_item(skip_button)

    button_id = "nav_finish" if is_last else "nav_next"
    button_label = "Finish ✅" if is_last else "Next"
    next_button = discord.ui.Button(
        label=button_label,
        style=discord.ButtonStyle.primary,
        custom_id=button_id,
        disabled=(required and not has_answer),
    )

    async def next_btn(inter, _btn):
        await inter.response.defer_update()
        if is_last:
            await controller.finish(inter, session)
        else:
            await controller.next(inter, session)

    next_button.callback = next_btn  # type: ignore[assignment]
    view.add_item(next_button)

    cancel_button = discord.ui.Button(
        label="Cancel",
        style=discord.ButtonStyle.danger,
        custom_id="nav_cancel",
    )

    async def cancel_btn(inter, _btn):
        await inter.response.defer_update()
        await controller.cancel(inter, session)

    cancel_button.callback = cancel_btn  # type: ignore[assignment]
    view.add_item(cancel_button)

    return content, view
