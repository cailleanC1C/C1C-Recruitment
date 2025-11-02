import logging
from types import SimpleNamespace

from modules.onboarding import logs


class _DummyResponse:
    def __init__(self, *, done: bool = False) -> None:
        self._done = done

    def is_done(self) -> bool:
        return self._done


class _DummyUser:
    def __init__(self) -> None:
        self.id = 789
        self.mention = "@Dummy"

    def __str__(self) -> str:  # pragma: no cover - simple repr
        return "Dummy#1234"


class _DummyView:
    pass


def _interaction(*, claimed: bool = False) -> SimpleNamespace:
    interaction = SimpleNamespace()
    interaction.data = {"custom_id": "welcome.panel.open", "component_type": 2}
    interaction.message = SimpleNamespace(id=321)
    interaction.id = 654
    interaction.user = _DummyUser()
    interaction.response = _DummyResponse()
    interaction.app_permissions = SimpleNamespace(value=42)
    if claimed:
        interaction._c1c_claimed = True  # type: ignore[attr-defined]
    return interaction


def test_log_view_error_sanitizes_reserved_keys(caplog):
    extra = {
        "thread": "<123>",
        "message": "payload",
        "custom": "value",
    }
    err = RuntimeError("boom")

    with caplog.at_level(logging.ERROR, logger="c1c.onboarding.logs"):
        logs.log_view_error(_interaction(), _DummyView(), err, tag="panel", extra=extra)

    record = caplog.records[-1]
    assert record.custom == "value"
    assert getattr(record, "context_thread", None) == "<123>"
    assert getattr(record, "context_message", None) == "payload"
    assert record.error_class == "RuntimeError"
    assert record.error_message == "boom"
    assert record.getMessage() == "welcome view error"


def test_log_view_error_preserves_existing_alias(caplog):
    extra = {
        "thread": "<456>",
        "context_thread": "<existing>",
    }
    err = ValueError("nope")

    with caplog.at_level(logging.ERROR, logger="c1c.onboarding.logs"):
        logs.log_view_error(_interaction(claimed=True), _DummyView(), err, tag="panel", extra=extra)

    record = caplog.records[-1]
    assert record.context_thread == "<existing>"
    # alias assigned for the reserved value should land on `_2`
    assert getattr(record, "context_thread_2") == "<456>"
    assert record.error_class == "ValueError"
    assert record.error_message == "nope"
    # the claimed flag should be available and truthy when set
    assert getattr(record, "claimed", None) is True
