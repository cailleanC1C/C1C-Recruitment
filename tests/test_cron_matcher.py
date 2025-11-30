from datetime import datetime, timezone

from modules.common.runtime import _cron_matches, _parse_cron_expression


def _dt(year: int, month: int, day: int, hour: int = 10, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_cron_matches_when_dom_and_dow_are_wildcards() -> None:
    schedule = _parse_cron_expression("0 10 * * *")

    assert _cron_matches(_dt(2024, 1, 1), schedule)
    assert _cron_matches(_dt(2024, 1, 2), schedule)
    assert not _cron_matches(_dt(2024, 1, 2, 11, 0), schedule)


def test_cron_matches_dom_only_when_dow_is_wildcard() -> None:
    schedule = _parse_cron_expression("0 10 1 * *")

    assert _cron_matches(_dt(2024, 1, 1), schedule)
    assert _cron_matches(_dt(2024, 2, 1), schedule)
    assert not _cron_matches(_dt(2024, 1, 2), schedule)


def test_cron_matches_dow_only_when_dom_is_wildcard() -> None:
    schedule = _parse_cron_expression("0 10 * * 1")

    assert _cron_matches(_dt(2024, 1, 1), schedule)  # Monday
    assert _cron_matches(_dt(2024, 1, 8), schedule)  # Monday
    assert not _cron_matches(_dt(2024, 1, 2), schedule)


def test_cron_matches_when_dom_or_dow_match() -> None:
    schedule = _parse_cron_expression("0 10 1 * 1")

    assert _cron_matches(_dt(2024, 1, 1), schedule)  # Both DOM and DOW
    assert _cron_matches(_dt(2024, 1, 8), schedule)  # DOW match
    assert _cron_matches(_dt(2024, 2, 1), schedule)  # DOM match
    assert not _cron_matches(_dt(2024, 1, 2), schedule)
