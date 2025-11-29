from datetime import datetime, timezone

import pytest

import shared.sheets.onboarding_sessions as sheet_module


@pytest.fixture()
def headers():
    return list(sheet_module.CANONICAL_COLUMNS)


def test_onboarding_sessions_row_mapping(monkeypatch, headers):
    fixed_now = "2025-01-05T12:00:00Z"
    monkeypatch.setattr(sheet_module, "_now_iso", lambda: fixed_now)

    payload = {
        "user_id": "123",
        "thread_id": "456",
        "panel_message_id": "789",
        "step_index": 15,
        "answers": {"foo": "bar"},
        "completed": True,
        "completed_at": datetime(2025, 1, 1, 10, 30, tzinfo=timezone.utc).isoformat(),
        "first_reminder_at": None,
        "warning_sent_at": None,
        "auto_closed_at": None,
    }

    row = sheet_module.build_row(payload, headers=headers)

    assert len(row) == len(headers)
    assert row[headers.index("answers_json")] == "{\"foo\":\"bar\"}"
    assert row[headers.index("updated_at")] == fixed_now
    assert row[headers.index("first_reminder_at")] == ""
    assert row[headers.index("warning_sent_at")] == ""
    assert row[headers.index("auto_closed_at")] == ""


class _FakeSheet:
    def __init__(self, rows):
        self._rows = rows

    def get_all_values(self):
        return self._rows


def test_onboarding_sessions_load_mapping(monkeypatch, headers):
    fixed_now = "2025-02-01T09:00:00Z"
    payload = {
        "user_id": 42,
        "thread_id": 84,
        "panel_message_id": 21,
        "step_index": 3,
        "answers": {"alpha": 1},
        "completed": False,
        "completed_at": None,
        "first_reminder_at": datetime(2025, 2, 1, 8, 0, tzinfo=timezone.utc).isoformat(),
        "warning_sent_at": "",
        "auto_closed_at": None,
    }

    monkeypatch.setattr(sheet_module, "_now_iso", lambda: fixed_now)

    row = sheet_module.build_row(payload, headers=headers)
    fake_sheet = _FakeSheet([headers, row])
    monkeypatch.setattr(sheet_module, "_sheet", lambda: fake_sheet)

    result = sheet_module.load(payload["user_id"], payload["thread_id"])

    assert result is not None
    assert result.get("answers", {}).get("alpha") == 1
    assert result.get("first_reminder_at")
    assert result.get("warning_sent_at") == ""
    assert result.get("auto_closed_at") == ""
    assert result.get("updated_at") == fixed_now
