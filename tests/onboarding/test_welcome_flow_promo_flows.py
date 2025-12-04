import asyncio
from types import SimpleNamespace

from modules.common import feature_flags
from modules.onboarding import thread_scopes, welcome_flow
from shared.sheets import onboarding_questions


class DummyThread(SimpleNamespace):
    def __init__(self, name: str = "R1234-user") -> None:
        super().__init__(id=999, name=name, parent=None)
        self.sent_messages: list[str | None] = []

    async def send(self, content=None, **_kwargs):
        self.sent_messages.append(content)


def test_resolve_onboarding_flow_welcome_scope(monkeypatch):
    monkeypatch.setattr(thread_scopes, "is_welcome_parent", lambda _thread: True)
    monkeypatch.setattr(thread_scopes, "is_promo_parent", lambda _thread: False)

    result = welcome_flow.resolve_onboarding_flow(DummyThread("W0001-user"))

    assert result.flow == "welcome"
    assert result.ticket_code is None


def test_resolve_onboarding_flow_maps_promo_prefix(monkeypatch):
    monkeypatch.setattr(thread_scopes, "is_welcome_parent", lambda _thread: False)
    monkeypatch.setattr(thread_scopes, "is_promo_parent", lambda _thread: True)

    result = welcome_flow.resolve_onboarding_flow(DummyThread("L9876-user"))

    assert result.flow == "promo.l"
    assert result.ticket_code == "L9876"


def test_resolve_onboarding_flow_handles_parse_failure(monkeypatch):
    monkeypatch.setattr(thread_scopes, "is_welcome_parent", lambda _thread: False)
    monkeypatch.setattr(thread_scopes, "is_promo_parent", lambda _thread: True)

    result = welcome_flow.resolve_onboarding_flow(DummyThread("no-ticket"))

    assert result.flow is None
    assert result.error == "promo_ticket_parse_failed"


def test_start_welcome_dialog_aborts_when_promo_disabled(monkeypatch):
    monkeypatch.setattr(thread_scopes, "is_welcome_parent", lambda _thread: False)
    monkeypatch.setattr(thread_scopes, "is_promo_parent", lambda _thread: True)

    thread = DummyThread("R2345-user")
    actor = SimpleNamespace(display_name="Recruit", bot=False)

    async def fake_locate(_thread):
        return SimpleNamespace()

    async def fake_send_log(level: str, **payload):
        recorded_logs.append(payload)

    recorded_logs: list[dict[str, object]] = []

    monkeypatch.setattr(welcome_flow, "locate_welcome_message", fake_locate)
    monkeypatch.setattr(welcome_flow, "extract_target_from_message", lambda _msg: (None, None))
    monkeypatch.setattr(welcome_flow.logs, "send_welcome_log", fake_send_log)
    monkeypatch.setattr(welcome_flow.logs, "send_welcome_exception", lambda *args, **kwargs: None)

    def fake_is_enabled(name: str) -> bool:
        return {"promo_enabled": False, "promo_dialog": True, "welcome_dialog": True}.get(name, True)

    monkeypatch.setattr(feature_flags, "is_enabled", fake_is_enabled)
    monkeypatch.setattr(onboarding_questions, "get_questions", lambda flow: (_ for _ in ()).throw(AssertionError("should not load questions")))

    asyncio.run(
        welcome_flow.start_welcome_dialog(
            thread,
            actor,
            source="ticket",
            bot=SimpleNamespace(),
        )
    )

    assert thread.sent_messages
    assert "promo dialogs are currently disabled" in (thread.sent_messages[0] or "").lower()
    assert recorded_logs and recorded_logs[0]["reason"] == "promo_enabled"


def test_start_welcome_dialog_uses_promo_subflow(monkeypatch):
    monkeypatch.setattr(thread_scopes, "is_welcome_parent", lambda _thread: False)
    monkeypatch.setattr(thread_scopes, "is_promo_parent", lambda _thread: True)

    thread = DummyThread("M6789-user")
    actor = SimpleNamespace(display_name="Recruit", bot=False)

    async def fake_locate(_thread):
        return SimpleNamespace()

    captured: dict[str, object] = {}

    async def fake_send_log(level: str, **payload):
        captured.setdefault("logs", []).append(payload)

    def fake_is_enabled(_name: str) -> bool:
        return True

    def fake_get_questions(flow: str):
        captured["flow"] = flow
        return [object()]

    class DummyController:
        def __init__(self, _bot, *, flow: str):
            self.flow = flow
            self._panel_messages = {}
            self._prefetched_panels = {}
            self._sources = {}

        async def run(self, *_args, **_kwargs):
            captured["controller_flow"] = self.flow
            return None

    monkeypatch.setattr(welcome_flow, "PromoController", DummyController)
    monkeypatch.setattr(welcome_flow, "WelcomeController", DummyController)
    monkeypatch.setattr(welcome_flow, "locate_welcome_message", fake_locate)
    monkeypatch.setattr(welcome_flow, "extract_target_from_message", lambda _msg: (None, None))
    monkeypatch.setattr(welcome_flow.logs, "send_welcome_log", fake_send_log)
    monkeypatch.setattr(welcome_flow.logs, "send_welcome_exception", lambda *args, **kwargs: None)
    async def fake_panel_log(**_kwargs):
        return None

    monkeypatch.setattr(welcome_flow.logs, "log_onboarding_panel_lifecycle", fake_panel_log)
    monkeypatch.setattr(feature_flags, "is_enabled", fake_is_enabled)
    monkeypatch.setattr(onboarding_questions, "get_questions", fake_get_questions)
    monkeypatch.setattr(onboarding_questions, "schema_hash", lambda flow: f"hash-{flow}")
    monkeypatch.setattr(welcome_flow, "_resolve_bot", lambda _thread: SimpleNamespace())
    monkeypatch.setattr(welcome_flow.panels, "register_panel_message", lambda *_args, **_kwargs: None)

    asyncio.run(
        welcome_flow.start_welcome_dialog(
            thread,
            actor,
            source="ticket",
            bot=SimpleNamespace(),
        )
    )

    assert captured.get("flow") == "promo.m"
    assert captured.get("controller_flow") == "promo.m"
    assert not thread.sent_messages
