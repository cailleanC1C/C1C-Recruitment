import logging

from modules.onboarding import logs


def test_log_view_error_sanitizes_reserved_keys(caplog):
    extra = {
        "thread": "<123>",
        "message": "payload",
        "custom": "value",
    }
    err = RuntimeError("boom")

    with caplog.at_level(logging.ERROR, logger="c1c.onboarding.logs"):
        logs.log_view_error(extra, err)

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
        logs.log_view_error(extra, err)

    record = caplog.records[-1]
    assert record.context_thread == "<existing>"
    # alias assigned for the reserved value should land on `_2`
    assert getattr(record, "context_thread_2") == "<456>"
    assert record.error_class == "ValueError"
    assert record.error_message == "nope"
