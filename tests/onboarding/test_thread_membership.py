import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from modules.onboarding import thread_membership


def test_skip_join_when_already_member():
    join_mock = AsyncMock()
    thread = SimpleNamespace(me=SimpleNamespace(joined=True), join=join_mock)

    joined, error = asyncio.run(thread_membership.ensure_thread_membership(thread))

    assert joined is True
    assert error is None
    join_mock.assert_not_called()


def test_join_called_when_not_member():
    join_mock = AsyncMock()
    thread = SimpleNamespace(me=None, join=join_mock)

    joined, error = asyncio.run(thread_membership.ensure_thread_membership(thread))

    assert joined is True
    assert error is None
    join_mock.assert_awaited_once()


def test_join_failure_returns_error():
    exc = RuntimeError("join failed")
    join_mock = AsyncMock(side_effect=exc)
    thread = SimpleNamespace(me=None, join=join_mock)

    joined, error = asyncio.run(thread_membership.ensure_thread_membership(thread))

    assert joined is False
    assert error is exc
    join_mock.assert_awaited_once()


def test_missing_join_returns_false():
    thread = SimpleNamespace(me=None, join=None)

    joined, error = asyncio.run(thread_membership.ensure_thread_membership(thread))

    assert joined is False
    assert error is None
