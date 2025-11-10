import asyncio
from types import SimpleNamespace

from modules.onboarding.controllers.welcome_controller import RollingCardSession


class DummyMessage:
    def __init__(self, channel):
        self.channel = channel
        self.content = ""
        self.view = None
        self.id = 1001

    async def edit(self, *, content=None, view=None):
        if content is not None:
            self.content = content
        self.view = view
        return self

    async def delete(self):  # pragma: no cover - unused but provided for completeness
        self.channel.sent_messages.remove(self)


class DummyThread:
    def __init__(self):
        self.id = 4242
        self.guild = None
        self.owner = SimpleNamespace(id=777)
        self.sent_messages: list[DummyMessage] = []

    async def send(self, content):
        message = DummyMessage(self)
        message.content = content
        self.sent_messages.append(message)
        return message


class DummyController:
    def __init__(self):
        self.recorded: list[tuple[int | None, str, str]] = []
        self.completed: list[int | None] = []

    def _record_rolling_answer(self, thread_id, question, value):
        self.recorded.append((thread_id, getattr(question, "qid", ""), value))

    def _complete_rolling(self, thread_id):
        self.completed.append(thread_id)


def _question(order: str, qid: str, label: str, rules: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        order=order,
        order_raw=order,
        qid=qid,
        label=label,
        qtype="number",
        type="number",
        help="",
        rules=rules,
        maxlen=None,
        validate="",
        required=True,
    )


def test_rolling_card_session_respects_goto_rules() -> None:
    controller = DummyController()
    thread = DummyThread()
    questions = [
        _question(
            "101",
            "importance",
            "How important is CvC to you?",
            rules="if importance <= 2 goto min_commit",
        ),
        _question("201", "min_cvc", "What’s the minimum CvC points you can commit to?"),
        _question("301", "min_commit", "Next milestone question"),
    ]

    async def run_flow() -> None:
        session = RollingCardSession(
            controller,
            thread=thread,
            owner=thread.owner,
            guild=None,
            questions=questions,
        )

        await session.start()
        assert thread.sent_messages[-1].content.startswith("**Onboarding • 1/3**")
        assert "How important is CvC" in thread.sent_messages[-1].content

        await session._store_answer_and_advance(questions[0], "2")

        # After answering 2, the follow-up question should be skipped via the goto rule.
        assert "Next milestone question" in thread.sent_messages[-1].content
        assert "What’s the minimum CvC points" not in thread.sent_messages[-1].content

    asyncio.run(run_flow())
