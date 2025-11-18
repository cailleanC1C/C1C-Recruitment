"""Persistent storage helpers for automated server map metadata."""

from __future__ import annotations

import asyncio
import os
from typing import Dict, Mapping

from shared.config import get_recruitment_sheet_id
from shared.sheets import async_core
import shared.config as shared_config

_STATE_LOCK = asyncio.Lock()


def _config_tab() -> str:
    raw = os.getenv("RECRUITMENT_CONFIG_TAB", "Config")
    text = (raw or "").strip()
    return text or "Config"


def _sheet_id() -> str:
    sheet_id = (get_recruitment_sheet_id() or "").strip()
    if not sheet_id:
        raise RuntimeError("RECRUITMENT_SHEET_ID not configured")
    return sheet_id


def _normalize_key(value: object) -> str:
    return str(value or "").strip().upper()


def _header_map(header: list[object]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    for idx, cell in enumerate(header):
        normalized = str(cell or "").strip().lower()
        if normalized:
            mapping[normalized] = idx
    return mapping


def _column_label(index: int) -> str:
    if index < 0:
        raise ValueError("column index must be >= 0")
    label = ""
    value = index
    while True:
        value, remainder = divmod(value, 26)
        label = chr(ord("A") + remainder) + label
        if value == 0:
            break
        value -= 1
    return label


def _row_lookup(matrix: list[list[object]], key_column: int) -> Dict[str, int]:
    lookup: Dict[str, int] = {}
    for row_index, row in enumerate(matrix[1:], start=2):
        cell = row[key_column] if key_column < len(row) else ""
        normalized = _normalize_key(cell)
        if normalized:
            lookup[normalized] = row_index
    return lookup


async def fetch_state() -> Dict[str, str]:
    """Return the Config sheet entries keyed by upper-case strings."""

    sheet_id = _sheet_id()
    tab_name = _config_tab()
    rows = await async_core.afetch_records(sheet_id, tab_name)
    state: Dict[str, str] = {}
    for row in rows:
        key_value: str | None = None
        stored_value: str | None = None
        fallback: str | None = None
        for column, raw_value in row.items():
            normalized = (column or "").strip().lower()
            text = str(raw_value or "").strip()
            if normalized == "key":
                key_value = _normalize_key(text)
            elif normalized in {"value", "val"}:
                stored_value = text
            elif fallback is None and text:
                fallback = text
        if key_value:
            if stored_value:
                state[key_value] = stored_value
            elif fallback:
                state[key_value] = fallback
    return state


async def update_state(entries: Mapping[str, str | None]) -> None:
    """Persist the supplied key/value pairs into the Config worksheet."""

    cleaned: Dict[str, str] = {}
    for key, value in entries.items():
        normalized = _normalize_key(key)
        if not normalized:
            continue
        cleaned[normalized] = "" if value is None else str(value).strip()
    if not cleaned:
        return

    sheet_id = _sheet_id()
    tab_name = _config_tab()

    async with _STATE_LOCK:
        matrix = await async_core.afetch_values(sheet_id, tab_name)
        if not matrix:
            raise RuntimeError("Recruitment Config worksheet is empty")
        header = matrix[0]
        header_mapping = _header_map(header)
        if "key" not in header_mapping:
            raise RuntimeError("Recruitment Config worksheet missing Key column")
        key_column = header_mapping["key"]
        value_column = header_mapping.get("value")
        if value_column is None:
            value_column = key_column + 1 if len(header) > key_column + 1 else 1
        rows = _row_lookup(matrix, key_column)
        worksheet = await async_core.aget_worksheet(sheet_id, tab_name)
        next_row = len(matrix) + 1
        max_column = max(value_column, key_column)

        for key, value in cleaned.items():
            row_number = rows.get(key)
            cell_value = value
            if row_number:
                target = f"{_column_label(value_column)}{row_number}"
                await async_core.acall_with_backoff(
                    worksheet.update,
                    target,
                    [[cell_value]],
                    value_input_option="RAW",
                )
            else:
                row = ["" for _ in range(max_column + 1)]
                row[key_column] = key
                row[value_column] = cell_value
                await async_core.acall_with_backoff(
                    worksheet.append_row,
                    row,
                    value_input_option="RAW",
                )
                rows[key] = next_row
                row_number = next_row
                next_row += 1
            if cell_value:
                shared_config._CONFIG[key] = cell_value  # type: ignore[attr-defined]
            else:
                shared_config._CONFIG.pop(key, None)  # type: ignore[attr-defined]
