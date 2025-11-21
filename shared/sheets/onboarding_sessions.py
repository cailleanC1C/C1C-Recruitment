from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import json
import os

from shared.sheets import core

TAB_NAME = "OnboardingSessions"
FIELDS = [
    "user_id",
    "thread_id",
    "panel_message_id",
    "step_index",
    "completed",
    "completed_at",
    "first_reminder_at",
    "warning_sent_at",
    "auto_closed_at",
    "answers_json",
    "updated_at",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sheet():
    sheet_id = os.getenv("ONBOARDING_SHEET_ID", "").strip()
    if not sheet_id:
        raise RuntimeError("ONBOARDING_SHEET_ID not set")
    return core.get_worksheet(sheet_id, TAB_NAME)


def load(user_id: int, thread_id: int) -> Optional[Dict[str, Any]]:
    worksheet = _sheet()
    rows = worksheet.get_all_records()
    for row in rows:
        try:
            row_user = int(row.get("user_id", 0))
            row_thread = int(row.get("thread_id", 0))
        except Exception:
            continue
        if row_user == int(user_id) and row_thread == int(thread_id):
            raw_answers = row.get("answers_json") or "{}"
            try:
                answers = json.loads(raw_answers)
            except Exception:
                answers = {}
            panel_raw = row.get("panel_message_id")
            try:
                panel_id = int(panel_raw) if panel_raw not in (None, "", 0) else None
            except Exception:
                panel_id = None
            completed_token = str(row.get("completed", "")).strip().lower()
            completed = completed_token in {"true", "1", "yes"}
            completed_at = row.get("completed_at") or None
            return {
                "user_id": row_user,
                "thread_id": row_thread,
                "panel_message_id": panel_id,
                "step_index": int(row.get("step_index", 0) or 0),
                "completed": completed,
                "completed_at": completed_at,
                "answers": answers,
            }
    return None


def save(payload: Dict[str, Any]) -> None:
    worksheet = _sheet()
    rows = worksheet.get_all_values()
    header = rows[0] if rows else FIELDS
    try:
        index_user = header.index("user_id")
    except ValueError:
        index_user = 0
    try:
        index_thread = header.index("thread_id")
    except ValueError:
        index_thread = 1

    target_row: Optional[int] = None
    for idx, row in enumerate(rows[1:], start=2):
        try:
            if int(row[index_user]) == int(payload["user_id"]) and int(row[index_thread]) == int(
                payload["thread_id"]
            ):
                target_row = idx
                break
        except Exception:
            continue

    record = {
        "user_id": int(payload["user_id"]),
        "thread_id": int(payload["thread_id"]),
        "panel_message_id": int(payload.get("panel_message_id") or 0),
        "step_index": int(payload.get("step_index", 0) or 0),
        "completed": bool(payload.get("completed", False)),
        "completed_at": payload.get("completed_at") or "",
        "first_reminder_at": payload.get("first_reminder_at") or "",
        "warning_sent_at": payload.get("warning_sent_at") or "",
        "auto_closed_at": payload.get("auto_closed_at") or "",
        "answers_json": json.dumps(payload.get("answers", {}), separators=(",", ":")),
        "updated_at": _now_iso(),
    }
    values = [record[key] for key in FIELDS]

    if target_row:
        worksheet.update(_range_for_row(target_row), [values])
        return

    if not rows:
        worksheet.update(_range_for_row(1), [FIELDS])
    worksheet.append_row(values)


def _range_for_row(row: int) -> str:
    end_column = _column_letter(len(FIELDS))
    return f"A{row}:{end_column}{row}"


def _column_letter(index: int) -> str:
    """Return spreadsheet column label for 1-indexed ``index``."""

    label = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        label = chr(65 + remainder) + label
    return label
