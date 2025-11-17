import logging

import pytest

from shared import watchdog


def test_watchdog_healthy_logs_info(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="watchdog")
    caplog.clear()
    monkeypatch.setattr(watchdog, "_LAST_HEALTHY_INFO_EMIT", 0.0, raising=False)

    with monkeypatch.context() as ctx:
        ctx.setattr(watchdog, "log", logging.getLogger("watchdog"))
        ctx.setattr(watchdog.time, "time", lambda: 1_000_000.0)
        watchdog._log_healthy(age=900.0, latency=0.1, since_ok=42.0, stall=600)

    messages = [record.getMessage() for record in caplog.records if record.name == "watchdog"]
    assert any("heartbeat old but latency healthy" in message for message in messages)


@pytest.mark.parametrize("delta", [0.0, 100.0, 599.9])
def test_watchdog_healthy_rate_limited(caplog, monkeypatch, delta):
    caplog.set_level(logging.INFO, logger="watchdog")
    caplog.clear()
    now = 2_000_000.0
    monkeypatch.setattr(watchdog, "_LAST_HEALTHY_INFO_EMIT", now - delta, raising=False)

    with monkeypatch.context() as ctx:
        ctx.setattr(watchdog, "log", logging.getLogger("watchdog"))
        ctx.setattr(watchdog.time, "time", lambda: now)
        watchdog._log_healthy(age=900.0, latency=0.1, since_ok=42.0, stall=600)

    messages = [record.getMessage() for record in caplog.records if record.name == "watchdog"]
    assert not messages
    assert watchdog._LAST_HEALTHY_INFO_EMIT == pytest.approx(now - delta)


def test_watchdog_healthy_resets_after_cooldown(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="watchdog")
    caplog.clear()
    initial = 3_000_000.0
    monkeypatch.setattr(watchdog, "_LAST_HEALTHY_INFO_EMIT", initial, raising=False)

    with monkeypatch.context() as ctx:
        ctx.setattr(watchdog, "log", logging.getLogger("watchdog"))
        ctx.setattr(watchdog.time, "time", lambda: initial + watchdog._HEALTHY_INFO_COOLDOWN + 1.0)
        watchdog._log_healthy(age=900.0, latency=0.1, since_ok=42.0, stall=600)

    messages = [record.getMessage() for record in caplog.records if record.name == "watchdog"]
    assert any("heartbeat old but latency healthy" in message for message in messages)
    assert watchdog._LAST_HEALTHY_INFO_EMIT == pytest.approx(
        initial + watchdog._HEALTHY_INFO_COOLDOWN + 1.0
    )
