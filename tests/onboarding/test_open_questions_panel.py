import asyncio

from modules.onboarding.ui.panels import OpenQuestionsPanelView


def test_open_questions_button_has_custom_id() -> None:
    async def runner() -> None:
        view = OpenQuestionsPanelView()
        button_ids = [
            getattr(child, "custom_id", None)
            for child in view.children
            if hasattr(child, "custom_id")
        ]

        assert OpenQuestionsPanelView.CUSTOM_ID in button_ids
        assert view.timeout is None

    asyncio.run(runner())
