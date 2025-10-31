import asyncio

import discord

from modules.onboarding.ui.select_renderer import SelectQuestionView, build_select_view
from shared.sheets.onboarding_questions import Option, Question


def _make_question(index: int) -> Question:
    return Question(
        flow="welcome",
        order=str(index),
        qid=f"q{index}",
        label=f"Question {index}",
        type="single-select",
        required=True,
        maxlen=None,
        validate=None,
        help=None,
        options=(Option(label="Option", value=f"opt-{index}"),),
        multi_max=None,
        rules=None,
    )


def _visibility_for(questions: list[Question]) -> dict[str, dict[str, str]]:
    return {question.qid: {"state": "show"} for question in questions}


def test_build_select_view_paginates_after_four_questions() -> None:
    questions = [_make_question(idx) for idx in range(6)]
    visibility = _visibility_for(questions)
    view: SelectQuestionView | None = None

    async def _runner() -> None:
        nonlocal view
        view = build_select_view(questions, visibility, answers={}, page=0)

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_runner())
    finally:
        asyncio.set_event_loop(None)
        loop.close()
    assert view is not None
    assert view.page == 0
    assert view.page_count == 2

    selects = [child for child in view.children if isinstance(child, discord.ui.Select)]
    assert len(selects) == 4
    assert {select.custom_id for select in selects} == {
        "ob.select.q0",
        "ob.select.q1",
        "ob.select.q2",
        "ob.select.q3",
    }

    buttons = [child for child in view.children if isinstance(child, discord.ui.Button)]
    custom_ids = {button.custom_id for button in buttons if button.custom_id}
    assert "ob.select.confirm" in custom_ids
    assert "ob.select.page.next" in custom_ids
    assert "ob.select.page.prev" not in custom_ids


def test_build_select_view_last_page_has_prev_button() -> None:
    questions = [_make_question(idx) for idx in range(6)]
    visibility = _visibility_for(questions)
    view: SelectQuestionView | None = None

    async def _runner() -> None:
        nonlocal view
        view = build_select_view(questions, visibility, answers={}, page=1)

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_runner())
    finally:
        asyncio.set_event_loop(None)
        loop.close()
    assert view is not None
    assert view.page == 1
    assert view.page_count == 2

    selects = [child for child in view.children if isinstance(child, discord.ui.Select)]
    assert len(selects) == 2
    assert {select.custom_id for select in selects} == {"ob.select.q4", "ob.select.q5"}

    buttons = [child for child in view.children if isinstance(child, discord.ui.Button)]
    custom_ids = {button.custom_id for button in buttons if button.custom_id}
    assert "ob.select.confirm" in custom_ids
    assert "ob.select.page.prev" in custom_ids
    assert "ob.select.page.next" not in custom_ids
