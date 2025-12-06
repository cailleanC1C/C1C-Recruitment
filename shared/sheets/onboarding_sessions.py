from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Iterable, Optional, Sequence

from shared.config import get_onboarding_sessions_tab, get_onboarding_sheet_id
from shared.sheets import core

log = logging.getLogger(__name__)

CANONICAL_COLUMNS: list[str] = [
    "thread_name",
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
_MISSING_COLUMN_LOGGED = False
_REQUIRED_COLUMNS = {"thread_id", "thread_name", "updated_at"}


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


def load(user_id: int | None, thread_id: int) -> Optional[Dict[str, Any]]:
    worksheet = _sheet()
    rows = worksheet.get_all_values()
    header = _validated_header(rows[0] if rows else [])
    if header is None:
        return None

    header_map = _header_index_map(header)
    target_row = _get_row_index_by_thread_id(rows[1:], header_map, thread_id)
    if target_row is None:
        return None

    row = rows[target_row]
    record = _record_from_row(row, header, header_map)
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
        "thread_name": record.get("thread_name") or "",
        "user_id": str(record.get("user_id") or ""),
        "thread_id": str(record.get("thread_id") or ""),
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


def load_all() -> list[Dict[str, Any]]:
    worksheet = _sheet()
    rows = worksheet.get_all_values()
    header = _validated_header(rows[0] if rows else [])
    if header is None:
        return []

    header_map = _header_index_map(header)
    sessions: list[Dict[str, Any]] = []

    for row in rows[1:]:
        record = _record_from_row(row, header, header_map)
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
                "thread_name": record.get("thread_name") or "",
                "user_id": str(record.get("user_id") or ""),
                "thread_id": str(record.get("thread_id") or ""),
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
    target_row = _get_row_index_by_thread_id(rows[1:], header_map, payload.get("thread_id"))

    existing: Dict[str, Any] = {}
    if target_row is not None:
        existing = _record_from_row(rows[target_row], header, header_map)

    record = _merge_record(existing, payload)
    values = build_row(record, headers=header)

    if target_row is not None:
        worksheet.update(_range_for_row(target_row + 1, header), [values])
    else:
        worksheet.append_row(values)

    log.info(
        "🧾 onboarding session saved • thread_id=%s • thread_name=%s • answers=%s",
        record.get("thread_id"),
        record.get("thread_name") or "",
        "yes" if record.get("answers") else "no",
    )


def build_row(payload: Dict[str, Any], *, headers: Sequence[str] | None = None) -> list[Any]:
    header = _normalize_header(headers or CANONICAL_COLUMNS)
    record = _record_from_payload(payload)
    return [record.get(col.strip().lower(), "") for col in header]


def _validate_header(header: Iterable[str]) -> Optional[list[str]]:
    normalized = _normalize_header(header)
    header_map = _header_index_map(normalized)
    missing = sorted(col for col in _REQUIRED_COLUMNS if col not in header_map)
    if missing:
        _log_missing_columns(missing)
        return None
    return normalized


def _validated_header(header: Iterable[str]) -> Optional[list[str]]:
    return _validate_header(header)


def _log_missing_columns(missing: Sequence[str]) -> None:
    global _MISSING_COLUMN_LOGGED
    if _MISSING_COLUMN_LOGGED:
        return
    _MISSING_COLUMN_LOGGED = True
    log.warning(
        "onboarding_sessions_misconfigured • missing_columns=%s",
        ",".join(sorted(missing)),
    )


def _normalize_header(header: Iterable[str]) -> list[str]:
    return [str(col or "").strip() for col in header]


def _record_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    answers = payload.get("answers")
    if answers is None and payload.get("answers_json"):
        try:
            answers = json.loads(payload.get("answers_json", "{}"))
        except Exception:
            answers = {}
    answers_json = payload.get("answers_json")
    if answers_json is None:
        answers_json = json.dumps(answers or {}, separators=(",", ":"))

    reminder_at = payload.get("first_reminder_at") or payload.get("empty_first_reminder_at") or ""
    warning_at = payload.get("warning_sent_at") or payload.get("empty_warning_sent_at") or ""
    auto_closed_at = payload.get("auto_closed_at") or ""
    updated_at = payload.get("updated_at") or _now_iso()
    if isinstance(updated_at, datetime):
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        updated_at = updated_at.isoformat()

    completed_value = payload.get("completed", False)
    if isinstance(completed_value, str):
        completed_value = completed_value.strip().lower() in {"true", "1", "yes"}

    return {
        "thread_name": str(payload.get("thread_name") or ""),
        "user_id": str(payload.get("user_id") or ""),
        "thread_id": str(payload.get("thread_id") or ""),
        "panel_message_id": _safe_int(payload.get("panel_message_id"), default="") or "",
        "step_index": _safe_int(payload.get("step_index"), default=0) or 0,
        "completed": bool(completed_value),
        "completed_at": payload.get("completed_at") or "",
        "answers_json": answers_json,
        "answers": answers or {},
        "updated_at": updated_at,
        "first_reminder_at": reminder_at,
        "warning_sent_at": warning_at,
        "auto_closed_at": auto_closed_at,
    }


def _record_from_row(row: Sequence[Any], header: Sequence[str], header_map: Dict[str, int]) -> Dict[str, Any]:
    record: Dict[str, Any] = {}
    for name in CANONICAL_COLUMNS:
        record[name] = _cell(row, header_map, name)
    return record


def _merge_record(existing: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    existing_answers = existing.get("answers_json") or existing.get("answers") or "{}"
    try:
        existing_answers = json.loads(existing_answers)
    except Exception:
        existing_answers = {}

    merged_payload: Dict[str, Any] = {
        "thread_name": payload.get("thread_name") or existing.get("thread_name") or "",
        "thread_id": payload.get("thread_id") or existing.get("thread_id") or "",
        "user_id": payload.get("user_id") or existing.get("user_id") or "",
        "panel_message_id": payload.get("panel_message_id") or existing.get("panel_message_id") or "",
        "step_index": payload.get("step_index", existing.get("step_index", 0)),
        "completed": payload.get("completed", existing.get("completed", False)),
        "completed_at": payload.get("completed_at") or existing.get("completed_at") or "",
        "answers": payload.get("answers", existing_answers),
        "updated_at": payload.get("updated_at") or existing.get("updated_at") or _now_iso(),
        "first_reminder_at": payload.get("first_reminder_at") or existing.get("first_reminder_at") or "",
        "warning_sent_at": payload.get("warning_sent_at") or existing.get("warning_sent_at") or "",
        "auto_closed_at": payload.get("auto_closed_at") or existing.get("auto_closed_at") or "",
    }
    return _record_from_payload(merged_payload)


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


def _get_row_index_by_thread_id(
    rows: Sequence[Sequence[Any]], header_map: Dict[str, int], thread_id: int | str | None
) -> Optional[int]:
    if thread_id is None:
        return None
    target_thread = str(thread_id).strip()
    if not target_thread:
        return None
    for idx, row in enumerate(rows, start=1):
        row_thread = str(_cell(row, header_map, "thread_id") or "").strip()
        if not row_thread:
            continue
        if row_thread == target_thread:
            return idx
    return None


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
