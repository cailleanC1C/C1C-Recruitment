from datetime import datetime, timezone
from types import SimpleNamespace

from modules.common import tickets as ticket_utils


def test_parse_ticket_code_matches_first_code():
    assert ticket_utils.parse_ticket_code("W0123 example") == "W0123"
    assert ticket_utils.parse_ticket_code("prefix m9999 move") == "M9999"
    assert ticket_utils.parse_ticket_code("no codes here") is None


def test_ticket_kind_and_url_helpers():
    thread = SimpleNamespace(id=222, name="W0123-new", guild=SimpleNamespace(id=111))
    ticket = ticket_utils.TicketThread(
        thread=thread,
        code="W0123",
        kind=ticket_utils.ticket_kind("W0123"),
        is_open=True,
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        member_ids=(),
    )

    assert ticket.kind == "welcome"
    assert ticket.url.endswith("/111/222")
