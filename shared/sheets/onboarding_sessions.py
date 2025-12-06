from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Iterable, Optional, Sequence

from shared.config import get_onboarding_sessions_tab, get_onboarding_sheet_id
from shared.sheets import core

log = logging.getLogger(__name__)

CANONICAL_COLUMNS: list[str] = [
    "user_id",
    "thread_id",
    "panel_message_id",
    "step_index",
    "completed",
    "completed_at",
    "answers_json",
    "updated_at",
    "first_reminder_at",
    "warning_sent_at",
    "auto_closed_at",
]

_HEADER_MISMATCH_LOGGED = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sheet():
    sheet_id = get_onboarding_sheet_id().strip()
    if not sheet_id:
        raise RuntimeError("ONBOARDING_SHEET_ID not set")
    tab_name = get_onboarding_sessions_tab().strip()
    if not tab_name:
        raise RuntimeError("ONBOARDING_SESSIONS_TAB not set in sheet/env config")
    return core.get_worksheet(sheet_id, tab_name)


def load(user_id: int, thread_id: int) -> Optional[Dict[str, Any]]:
    worksheet = _sheet()
    rows = worksheet.get_all_values()
    header = _validated_header(rows[0] if rows else [])
    if header is None:
        return None

    header_map = _header_index_map(header)

    for row in rows[1:]:
        row_user = _safe_int(_cell(row, header_map, "user_id"))
        row_thread = _safe_int(_cell(row, header_map, "thread_id"))
        if row_user != int(user_id) or row_thread != int(thread_id):
            continue

        record = _record_from_row(row, header)
        raw_answers = record.get("answers_json") or "{}"
        try:
            answers = json.loads(raw_answers)
        except Exception:
            answers = {}

        panel_id = _safe_int(record.get("panel_message_id"))
        completed_token = str(record.get("completed", "")).strip().lower()
        completed = completed_token in {"true", "1", "yes", "true"}
        completed_at = record.get("completed_at") or None
        return {
            "user_id": row_user,
            "thread_id": row_thread,
            "panel_message_id": panel_id if panel_id not in (None, 0) else None,
            "step_index": _safe_int(record.get("step_index"), default=0),
            "completed": completed,
            "completed_at": completed_at,
            "updated_at": record.get("updated_at") or "",
            "first_reminder_at": record.get("first_reminder_at") or "",
            "warning_sent_at": record.get("warning_sent_at") or "",
            "auto_closed_at": record.get("auto_closed_at") or "",
            "answers": answers,
        }
    return None


def load_all() -> list[Dict[str, Any]]:
    worksheet = _sheet()
    rows = worksheet.get_all_values()
    header = _validated_header(rows[0] if rows else [])
    if header is None:
        return []

    header_map = _header_index_map(header)
    sessions: list[Dict[str, Any]] = []

    for row in rows[1:]:
        record = _record_from_row(row, header)
        raw_answers = record.get("answers_json") or "{}"
        try:
            answers = json.loads(raw_answers)
        except Exception:
            answers = {}

        panel_id = _safe_int(record.get("panel_message_id"))
        completed_token = str(record.get("completed", "")).strip().lower()
        completed = completed_token in {"true", "1", "yes", "true"}
        completed_at = record.get("completed_at") or None

        sessions.append(
            {
                "user_id": _safe_int(_cell(row, header_map, "user_id")),
                "thread_id": _safe_int(_cell(row, header_map, "thread_id")),
                "panel_message_id": panel_id if panel_id not in (None, 0) else None,
                "step_index": _safe_int(record.get("step_index"), default=0),
                "completed": completed,
                "completed_at": completed_at,
                "updated_at": record.get("updated_at") or "",
                "first_reminder_at": record.get("first_reminder_at") or "",
                "warning_sent_at": record.get("warning_sent_at") or "",
                "auto_closed_at": record.get("auto_closed_at") or "",
                "answers": answers,
            }
        )

    return sessions


def save(payload: Dict[str, Any]) -> None:
    worksheet = _sheet()
    rows = worksheet.get_all_values()
    header = _validated_header(rows[0] if rows else [])
    if header is None:
        return

    header_map = _header_index_map(header)

    target_row: Optional[int] = None
    for idx, row in enumerate(rows[1:], start=2):
        row_user = _safe_int(_cell(row, header_map, "user_id"))
        row_thread = _safe_int(_cell(row, header_map, "thread_id"))
        if row_user == int(payload["user_id"]) and row_thread == int(payload["thread_id"]):
            target_row = idx
            break

    values = build_row(payload, headers=header)

    if target_row:
        worksheet.update(_range_for_row(target_row, header), [values])
        log.info(
            "🧾 onboarding session saved • thread_id=%s answers=%s",
            payload.get("thread_id"),
            "yes" if payload.get("answers") else "no",
        )
        return

    if not rows:
        worksheet.update(_range_for_row(1, header), [_normalize_header(header)])
    worksheet.append_row(values)
    log.info(
        "🧾 onboarding session saved • thread_id=%s answers=%s",
        payload.get("thread_id"),
        "yes" if payload.get("answers") else "no",
    )


def build_row(payload: Dict[str, Any], *, headers: Sequence[str] | None = None) -> list[Any]:
    header = _normalize_header(headers or CANONICAL_COLUMNS)
    record = _record_from_payload(payload)
    return [record.get(col.strip().lower(), "") for col in header]


def _validate_header(header: Iterable[str]) -> Optional[list[str]]:
    normalized = _normalize_header(header)
    if _header_matches(normalized):
        return normalized

    _log_header_mismatch(normalized)
    return None


def _header_matches(header: Sequence[str]) -> bool:
    normalized = [col.strip().lower() for col in header]
    canonical = [col.lower() for col in CANONICAL_COLUMNS]
    return normalized == canonical


def _validated_header(header: Iterable[str]) -> Optional[list[str]]:
    return _validate_header(header)


def _log_header_mismatch(header: Sequence[str]) -> None:
    global _HEADER_MISMATCH_LOGGED
    if _HEADER_MISMATCH_LOGGED:
        return
    _HEADER_MISMATCH_LOGGED = True
    observed = ", ".join(_normalize_header(header)) or "<empty>"
    expected = ", ".join(CANONICAL_COLUMNS)
    log.error(
        "❌ OnboardingSessions header mismatch; expected [%s] but found [%s]. Skipping persistence.",
        expected,
        observed,
    )


def _normalize_header(header: Iterable[str]) -> list[str]:
    return [str(col or "").strip() for col in header]


def _record_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    answers_json = json.dumps(payload.get("answers", {}), separators=(",", ":"))
    reminder_at = payload.get("first_reminder_at") or payload.get("empty_first_reminder_at") or ""
    warning_at = payload.get("warning_sent_at") or payload.get("empty_warning_sent_at") or ""
    auto_closed_at = payload.get("auto_closed_at") or ""
    updated_at = payload.get("updated_at") or _now_iso()
    if isinstance(updated_at, datetime):
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        updated_at = updated_at.isoformat()

    return {
        "user_id": int(payload["user_id"]),
        "thread_id": int(payload["thread_id"]),
        "panel_message_id": int(payload.get("panel_message_id") or 0),
        "step_index": int(payload.get("step_index", 0) or 0),
        "completed": bool(payload.get("completed", False)),
        "completed_at": payload.get("completed_at") or "",
        "answers_json": answers_json,
        "updated_at": updated_at,
        "first_reminder_at": reminder_at,
        "warning_sent_at": warning_at,
        "auto_closed_at": auto_closed_at,
    }


def _record_from_row(row: Sequence[Any], header: Sequence[str]) -> Dict[str, Any]:
    header_map = _header_index_map(header)
    return {name: _cell(row, header_map, name) for name in CANONICAL_COLUMNS}


def _header_index_map(header: Sequence[str]) -> Dict[str, int]:
    return {name.strip().lower(): idx for idx, name in enumerate(header)}


def _cell(row: Sequence[Any], header_map: Dict[str, int], key: str) -> Any:
    idx = header_map.get(key.lower())
    if idx is None or idx >= len(row):
        return ""
    try:
        return row[idx]
    except Exception:
        return ""


def _safe_int(value: Any, *, default: int | None = None) -> int | None:
    try:
        return int(value)
    except Exception:
        return default


def _range_for_row(row: int, header: Sequence[str]) -> str:
    end_column = _column_letter(len(header))
    return f"A{row}:{end_column}{row}"


def _column_letter(index: int) -> str:
    """Return spreadsheet column label for 1-indexed ``index``."""

    label = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        label = chr(65 + remainder) + label
    return label
