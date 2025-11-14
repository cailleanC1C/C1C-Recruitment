import datetime as dt

from modules.onboarding.watcher_welcome import (
    _NO_PLACEMENT_TAG,
    _determine_reservation_decision,
)
from shared.sheets import reservations as reservations_sheets


def _make_reservation(tag: str, *, created: dt.datetime | None = None) -> reservations_sheets.ReservationRow:
    created_at = created or dt.datetime.now(dt.timezone.utc)
    return reservations_sheets.ReservationRow(
        row_number=2,
        thread_id="123",
        ticket_user_id=111,
        recruiter_id=222,
        clan_tag=tag,
        reserved_until=None,
        created_at=created_at,
        status="active",
        notes="",
        username_snapshot="Tester",
        raw=[],
    )


def test_decision_reservation_same_clan() -> None:
    row = _make_reservation("C1CE")
    decision = _determine_reservation_decision(
        "C1CE",
        row,
        no_placement_tag=_NO_PLACEMENT_TAG,
        final_is_real=True,
    )
    assert decision.label == "same"
    assert decision.status == "closed_same_clan"
    assert decision.open_deltas == {}
    assert decision.recompute_tags == ["C1CE"]


def test_decision_reservation_moved_clan() -> None:
    row = _make_reservation("C1CE")
    decision = _determine_reservation_decision(
        "VAGR",
        row,
        no_placement_tag=_NO_PLACEMENT_TAG,
        final_is_real=True,
    )
    assert decision.label == "moved"
    assert decision.status == "closed_other_clan"
    assert decision.open_deltas == {"C1CE": 1, "VAGR": -1}
    assert set(decision.recompute_tags) == {"C1CE", "VAGR"}


def test_decision_no_reservation_final_real_clan() -> None:
    decision = _determine_reservation_decision(
        "C1CE",
        None,
        no_placement_tag=_NO_PLACEMENT_TAG,
        final_is_real=True,
    )
    assert decision.label == "none"
    assert decision.status is None
    assert decision.open_deltas == {"C1CE": -1}
    assert decision.recompute_tags == ["C1CE"]


def test_decision_reservation_cancelled_with_no_clan() -> None:
    row = _make_reservation("MART")
    decision = _determine_reservation_decision(
        _NO_PLACEMENT_TAG,
        row,
        no_placement_tag=_NO_PLACEMENT_TAG,
        final_is_real=False,
    )
    assert decision.label == "cancelled"
    assert decision.status == "cancelled"
    assert decision.open_deltas == {"MART": 1}
    assert decision.recompute_tags == ["MART"]


def test_decision_no_reservation_no_clan() -> None:
    decision = _determine_reservation_decision(
        _NO_PLACEMENT_TAG,
        None,
        no_placement_tag=_NO_PLACEMENT_TAG,
        final_is_real=False,
    )
    assert decision.label == "none"
    assert decision.status is None
    assert decision.open_deltas == {}
    assert decision.recompute_tags == []
