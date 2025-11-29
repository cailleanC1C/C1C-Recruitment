import asyncio
from types import SimpleNamespace

import discord

from modules.onboarding.ui import summary_retry


class StubResponse:
    def __init__(self) -> None:
        self.sent: list[tuple[str, bool]] = []
        self.edited: list[tuple[discord.Embed | None, object | None]] = []

    async def send_message(self, content: str, *, ephemeral: bool = False) -> None:
        self.sent.append((content, ephemeral))

    async def edit_message(self, *, embed: discord.Embed | None = None, view=None) -> None:
        self.edited.append((embed, view))


class StubStore:
    def __init__(self, session: object | None) -> None:
        self._session = session
        self.ended: list[int] = []

    def get(self, thread_id: int):
        return self._session

    def end(self, thread_id: int) -> None:
        self.ended.append(thread_id)


def _interaction(user: object, channel: object) -> SimpleNamespace:
    return SimpleNamespace(user=user, channel=channel, response=StubResponse())


def test_retry_requires_recruiter(monkeypatch) -> None:
    monkeypatch.setattr(summary_retry.rbac, "is_recruiter", lambda user: False)
    channel = SimpleNamespace(id=9)
    monkeypatch.setattr(summary_retry.discord, "Thread", channel.__class__)
    monkeypatch.setattr(summary_retry.discord, "TextChannel", channel.__class__)
    interaction = _interaction(SimpleNamespace(), channel)

    async def runner() -> bool:
        view = summary_retry.RetryWelcomeSummaryView(thread_id=9, timeout=1)
        return await view.interaction_check(interaction)

    allowed = asyncio.run(runner())

    assert not allowed
    assert interaction.response.sent[-1][0] == "Only recruiters can retry the summary."


def test_retry_happy_path(monkeypatch) -> None:
    embed = discord.Embed(description="rebuilt")
    built: dict[str, object] = {}

    def fake_build_summary_embed(**kwargs):
        built.update(kwargs)
        return embed

    session = SimpleNamespace(answers={"w_ign": "Recruit"}, schema_hash="hash", visibility={})
    store = StubStore(session)

    monkeypatch.setattr(summary_retry.rbac, "is_recruiter", lambda user: True)
    monkeypatch.setattr(summary_retry, "store", store)
    monkeypatch.setattr(summary_retry, "build_summary_embed", fake_build_summary_embed)

    channel_type = type(
        "FakeChannel",
        (),
        {},
    )
    thread = channel_type()
    thread.id = 42
    thread.owner = SimpleNamespace()
    monkeypatch.setattr(summary_retry.discord, "Thread", channel_type)
    monkeypatch.setattr(summary_retry.discord, "TextChannel", channel_type)
    interaction = _interaction(SimpleNamespace(), thread)

    state: dict[str, object] = {}

    async def runner() -> None:
        view = summary_retry.RetryWelcomeSummaryView(thread_id=42, timeout=1)
        state["view"] = view
        button = view.children[0]
        await button.callback(interaction)

    asyncio.run(runner())

    assert built.get("flow") == "welcome"
    assert built.get("answers") == session.answers
    assert interaction.response.edited[-1][0] is embed
    assert interaction.response.edited[-1][1] is None
    assert store.ended == [42]
    assert state["view"]._retry_used is True


def test_retry_missing_session(monkeypatch) -> None:
    monkeypatch.setattr(summary_retry.rbac, "is_recruiter", lambda user: True)
    monkeypatch.setattr(summary_retry, "store", StubStore(None))

    channel_type = type("MissingSessionChannel", (), {})
    thread = channel_type()
    thread.id = 101
    monkeypatch.setattr(summary_retry.discord, "Thread", channel_type)
    monkeypatch.setattr(summary_retry.discord, "TextChannel", channel_type)
    interaction = _interaction(SimpleNamespace(), thread)

    async def runner() -> None:
        view = summary_retry.RetryWelcomeSummaryView(thread_id=101, timeout=1)
        button = view.children[0]
        await button.callback(interaction)

    asyncio.run(runner())

    assert interaction.response.sent[-1][0] == "No onboarding answers found for this thread."


def test_retry_failure_soft_fallback(monkeypatch) -> None:
    def failing_builder(**_: object) -> discord.Embed:
        raise RuntimeError("boom")

    session = SimpleNamespace(answers={}, schema_hash="hash", visibility={})
    store = StubStore(session)

    monkeypatch.setattr(summary_retry.rbac, "is_recruiter", lambda user: True)
    monkeypatch.setattr(summary_retry, "store", store)
    monkeypatch.setattr(summary_retry, "build_summary_embed", failing_builder)

    channel_type = type("FailureChannel", (), {})
    thread = channel_type()
    thread.id = 7
    monkeypatch.setattr(summary_retry.discord, "Thread", channel_type)
    monkeypatch.setattr(summary_retry.discord, "TextChannel", channel_type)
    interaction = _interaction(SimpleNamespace(), thread)

    async def runner() -> None:
        view = summary_retry.RetryWelcomeSummaryView(thread_id=7, timeout=1)
        button = view.children[0]
        await button.callback(interaction)

    asyncio.run(runner())

    assert interaction.response.sent[-1][0].startswith("Couldn’t rebuild the summary")
    assert store.ended == []
