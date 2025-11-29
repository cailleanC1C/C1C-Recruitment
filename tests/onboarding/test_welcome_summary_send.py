import asyncio
from types import SimpleNamespace

import discord

from modules.onboarding.controllers import welcome_controller


class DummyThread:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []
        self.raise_on_send: Exception | None = None

    async def send(self, **kwargs: object) -> object:
        if self.raise_on_send is not None:
            raise self.raise_on_send
        self.sent.append(kwargs)
        return SimpleNamespace(**kwargs)


def test_send_welcome_summary_safe_success(monkeypatch: object) -> None:
    controller = welcome_controller.WelcomeController(SimpleNamespace())
    embed = discord.Embed(title="ok")
    monkeypatch.setattr(welcome_controller, "build_summary_embed", lambda **_: embed)
    thread = DummyThread()

    success = asyncio.run(
        controller._send_welcome_summary_safe(
            thread=thread,
            answers={"foo": "bar"},
            author=None,
            schema_hash="hash",
            visibility=None,
            content="hi",
        )
    )

    assert success is True
    assert thread.sent == [{"content": "hi", "embed": embed, "allowed_mentions": None}]


def test_send_welcome_summary_safe_build_failure(monkeypatch: object) -> None:
    controller = welcome_controller.WelcomeController(SimpleNamespace())
    fallback = discord.Embed(title="fallback")
    monkeypatch.setattr(
        welcome_controller,
        "build_summary_embed",
        lambda **_: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(welcome_controller, "_fallback_welcome_embed", lambda _author: fallback)
    thread = DummyThread()

    success = asyncio.run(
        controller._send_welcome_summary_safe(
            thread=thread,
            answers={},
            author=None,
            schema_hash="hash",
            visibility=None,
        )
    )

    assert success is True
    assert thread.sent == [{"content": None, "embed": fallback, "allowed_mentions": None}]


def test_send_welcome_summary_safe_send_failure(monkeypatch: object) -> None:
    controller = welcome_controller.WelcomeController(SimpleNamespace())
    embed = discord.Embed(title="ok")
    monkeypatch.setattr(welcome_controller, "build_summary_embed", lambda **_: embed)
    thread = DummyThread()
    thread.raise_on_send = RuntimeError("boom")

    success = asyncio.run(
        controller._send_welcome_summary_safe(
            thread=thread,
            answers={},
            author=None,
            schema_hash="hash",
            visibility=None,
        )
    )

    assert success is False
    assert thread.sent == []
