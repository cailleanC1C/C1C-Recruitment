from __future__ import annotations

from modules.ops import cleanup_watcher


def test_get_cleanup_interval_hours_default(monkeypatch):
    monkeypatch.delenv("CLEANUP_INTERVAL_HOURS", raising=False)
    assert cleanup_watcher.get_cleanup_interval_hours() == 24


def test_get_cleanup_interval_hours_invalid(monkeypatch):
    monkeypatch.setenv("CLEANUP_INTERVAL_HOURS", "not-a-number")
    assert cleanup_watcher.get_cleanup_interval_hours() == 24


def test_get_cleanup_interval_hours_minimum(monkeypatch):
    monkeypatch.setenv("CLEANUP_INTERVAL_HOURS", "0")
    assert cleanup_watcher.get_cleanup_interval_hours() == 1


def test_get_cleanup_thread_ids(monkeypatch):
    monkeypatch.setenv("CLEANUP_THREAD_IDS", "123 , abc , 456,  789 ")
    assert cleanup_watcher.get_cleanup_thread_ids() == [123, 456, 789]


def test_get_cleanup_thread_ids_empty(monkeypatch):
    monkeypatch.delenv("CLEANUP_THREAD_IDS", raising=False)
    assert cleanup_watcher.get_cleanup_thread_ids() == []
