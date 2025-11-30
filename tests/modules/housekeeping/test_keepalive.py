from modules.housekeeping import keepalive


def test_get_keepalive_interval_hours_default(monkeypatch):
    monkeypatch.delenv("KEEPALIVE_INTERVAL_HOURS", raising=False)
    assert keepalive.get_keepalive_interval_hours() == 144


def test_get_keepalive_interval_hours_invalid(monkeypatch):
    monkeypatch.setenv("KEEPALIVE_INTERVAL_HOURS", "oops")
    assert keepalive.get_keepalive_interval_hours() == 144


def test_get_keepalive_interval_hours_minimum(monkeypatch):
    monkeypatch.setenv("KEEPALIVE_INTERVAL_HOURS", "0")
    assert keepalive.get_keepalive_interval_hours() == 1


def test_get_keepalive_channel_ids(monkeypatch):
    monkeypatch.setenv("KEEPALIVE_CHANNEL_IDS", "123, abc, 456")
    assert keepalive.get_keepalive_channel_ids() == {123, 456}


def test_get_keepalive_thread_ids(monkeypatch):
    monkeypatch.setenv("KEEPALIVE_THREAD_IDS", "")
    assert keepalive.get_keepalive_thread_ids() == set()
