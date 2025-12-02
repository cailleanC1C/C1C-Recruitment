from datetime import datetime, timezone
from types import SimpleNamespace

from modules.common.tickets import TicketThread
from modules.recruitment.reporting import open_ticket_report as report


def _ticket(name: str, kind: str, *, open_state: bool, minutes: int = 0) -> TicketThread:
    created = datetime(2025, 1, 1, 12, minutes, tzinfo=timezone.utc)
    thread = SimpleNamespace(id=minutes + 1, name=name, guild=SimpleNamespace(id=999))
    return TicketThread(
        thread=thread,
        code=name.split("-", 1)[0].upper(),
        kind=kind,
        is_open=open_state,
        created_at=created,
        member_ids=(),
    )


def test_group_tickets_sorts_and_filters():
    tickets = [
        _ticket("W0002-b", "welcome", open_state=True, minutes=10),
        _ticket("W0001-a", "welcome", open_state=True, minutes=5),
        _ticket("M0001-move", "move", open_state=True, minutes=20),
        _ticket("Closed-W0003", "welcome", open_state=False, minutes=30),
    ]

    welcome, move_requests = report._group_tickets(tickets)

    assert [item.code for item in welcome] == ["W0001", "W0002"]
    assert [item.code for item in move_requests] == ["M0001"]


def test_render_report_handles_empty_sections():
    content = report._render_report([], [])

    assert "Welcome" in content
    assert "None right now" in content
    assert "last updated" in content
