"""Sheet access helpers for the Shard & Mercy tracker."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence

from shared.config import cfg as runtime_config, get_milestones_sheet_id
from shared.sheets import async_core

log = logging.getLogger("c1c.shards.data")
_CONFIG_LOG_EMITTED = False

EXPECTED_HEADERS: List[str] = [
    "discord_id",
    "username_snapshot",
    "ancients_owned",
    "voids_owned",
    "sacreds_owned",
    "primals_owned",
    "ancients_since_lego",
    "voids_since_lego",
    "sacreds_since_lego",
    "primals_since_lego",
    "primals_since_mythic",
    "last_ancient_lego_iso",
    "last_void_lego_iso",
    "last_sacred_lego_iso",
    "last_primal_lego_iso",
    "last_primal_mythic_iso",
    "last_updated_iso",
]


@dataclass(slots=True)
class ShardTrackerConfig:
    sheet_id: str
    tab_name: str
    channel_id: int


@dataclass(slots=True)
class ShardRecord:
    header: Sequence[str]
    discord_id: int
    username_snapshot: str
    row_number: int = 0
    ancients_owned: int = 0
    voids_owned: int = 0
    sacreds_owned: int = 0
    primals_owned: int = 0
    ancients_since_lego: int = 0
    voids_since_lego: int = 0
    sacreds_since_lego: int = 0
    primals_since_lego: int = 0
    primals_since_mythic: int = 0
    last_ancient_lego_iso: str = ""
    last_void_lego_iso: str = ""
    last_sacred_lego_iso: str = ""
    last_primal_lego_iso: str = ""
    last_primal_mythic_iso: str = ""
    last_updated_iso: str = ""

    def snapshot_name(self, value: str) -> None:
        self.username_snapshot = (value or "").strip()[:64]

    def to_row(self) -> List[str]:
        mapping = {
            "discord_id": str(self.discord_id),
            "username_snapshot": self.username_snapshot,
            "ancients_owned": str(max(self.ancients_owned, 0)),
            "voids_owned": str(max(self.voids_owned, 0)),
            "sacreds_owned": str(max(self.sacreds_owned, 0)),
            "primals_owned": str(max(self.primals_owned, 0)),
            "ancients_since_lego": str(max(self.ancients_since_lego, 0)),
            "voids_since_lego": str(max(self.voids_since_lego, 0)),
            "sacreds_since_lego": str(max(self.sacreds_since_lego, 0)),
            "primals_since_lego": str(max(self.primals_since_lego, 0)),
            "primals_since_mythic": str(max(self.primals_since_mythic, 0)),
            "last_ancient_lego_iso": self.last_ancient_lego_iso,
            "last_void_lego_iso": self.last_void_lego_iso,
            "last_sacred_lego_iso": self.last_sacred_lego_iso,
            "last_primal_lego_iso": self.last_primal_lego_iso,
            "last_primal_mythic_iso": self.last_primal_mythic_iso,
            "last_updated_iso": self.last_updated_iso,
        }
        return [str(mapping.get(name, "")) for name in self.header]


class ShardTrackerConfigError(RuntimeError):
    """Raised when the shard tracker configuration is incomplete."""


class ShardTrackerSheetError(RuntimeError):
    """Raised when the shard tracker worksheet schema is invalid."""


class ShardSheetStore:
    """Async facade for the shard tracker worksheet."""

    _CONFIG_TTL = 300

    def __init__(self) -> None:
        self._config_cache: ShardTrackerConfig | None = None
        self._config_ts = 0.0
        self._config_lock = asyncio.Lock()
        self._sheet_lock = asyncio.Lock()

    async def get_config(self) -> ShardTrackerConfig:
        async with self._config_lock:
            if self._config_cache and (time.time() - self._config_ts) < self._CONFIG_TTL:
                return self._config_cache

            sheet_id = (get_milestones_sheet_id() or "").strip()
            tab_value = _config_value("shard_mercy_tab", "")
            tab_name = str(tab_value or "").strip()

            raw_env = (os.getenv("SHARD_MERCY_CHANNEL_ID") or "").strip()
            env_channel_id = _parse_channel_id(raw_env)

            sheet_channel_value = _config_value("shard_mercy_channel_id", "")
            sheet_raw = str(sheet_channel_value or "").strip()
            sheet_has_row = bool(sheet_raw)
            sheet_channel_id = _parse_channel_id(sheet_channel_value)

            channel_id = env_channel_id or sheet_channel_id
            source = "env" if env_channel_id else ("sheet" if sheet_channel_id else "missing")

            _log_config_snapshot(
                tab_name=tab_name,
                source=source,
                sheet_has_row=sheet_has_row,
                raw_env=raw_env,
                raw_sheet=sheet_raw,
                parsed_channel_id=channel_id,
            )

            if not sheet_id:
                raise ShardTrackerConfigError("MILESTONES_SHEET_ID missing")

            if not tab_name:
                raise ShardTrackerConfigError("SHARD_MERCY_TAB missing in milestones Config tab")

            if channel_id <= 0:
                raise ShardTrackerConfigError("SHARD_MERCY_CHANNEL_ID missing or invalid")

            config = ShardTrackerConfig(
                sheet_id=sheet_id,
                tab_name=tab_name,
                channel_id=channel_id,
            )
            self._config_cache = config
            self._config_ts = time.time()
            return config

    async def load_record(self, discord_id: int, username: str) -> ShardRecord:
        config = await self.get_config()
        matrix = await async_core.afetch_values(config.sheet_id, config.tab_name)
        if not matrix:
            raise ShardTrackerSheetError("Shard tracker worksheet is empty; headers required")
        header = [self._normalize(cell) for cell in matrix[0]]
        if header != EXPECTED_HEADERS:
            raise ShardTrackerSheetError("Shard tracker headers do not match EXPECTED_HEADERS")
        header_map = {name: idx for idx, name in enumerate(header)}
        row_number = 1
        target_row: Sequence[str] | None = None
        for offset, row in enumerate(matrix[1:], start=2):
            row_number = offset
            if self._matches_user(row, header_map, discord_id):
                target_row = row
                break
        if target_row is None:
            record = self._new_record(header, discord_id, username)
            new_row_number = await self._append_row(config, record)
            record.row_number = new_row_number
            return record
        return self._row_to_record(header, header_map, row_number, target_row, discord_id, username)

    async def save_record(self, config: ShardTrackerConfig, record: ShardRecord) -> None:
        record.last_updated_iso = _now_iso()
        range_label = f"A{record.row_number}:Q{record.row_number}"
        row = record.to_row()
        worksheet = await async_core.aget_worksheet(config.sheet_id, config.tab_name)
        async with self._sheet_lock:
            await async_core.acall_with_backoff(
                worksheet.update,
                range_label,
                [row],
                value_input_option="RAW",
            )

    async def _append_row(self, config: ShardTrackerConfig, record: ShardRecord) -> int:
        worksheet = await async_core.aget_worksheet(config.sheet_id, config.tab_name)
        async with self._sheet_lock:
            matrix = await async_core.afetch_values(config.sheet_id, config.tab_name)
            new_row_number = len(matrix) + 1 if matrix else 1
            await async_core.acall_with_backoff(
                worksheet.append_row,
                record.to_row(),
                value_input_option="RAW",
            )
        return new_row_number

    def _row_to_record(
        self,
        header: Sequence[str],
        header_map: Dict[str, int],
        row_number: int,
        row: Sequence[str],
        discord_id: int,
        username: str,
    ) -> ShardRecord:
        def cell(name: str) -> str:
            idx = header_map.get(name, -1)
            if idx < 0 or idx >= len(row):
                return ""
            return str(row[idx] or "").strip()

        record = ShardRecord(
            header=header,
            row_number=row_number,
            discord_id=discord_id,
            username_snapshot=cell("username_snapshot") or (username or "")[:64],
            ancients_owned=self._parse_int(cell("ancients_owned")),
            voids_owned=self._parse_int(cell("voids_owned")),
            sacreds_owned=self._parse_int(cell("sacreds_owned")),
            primals_owned=self._parse_int(cell("primals_owned")),
            ancients_since_lego=self._parse_int(cell("ancients_since_lego")),
            voids_since_lego=self._parse_int(cell("voids_since_lego")),
            sacreds_since_lego=self._parse_int(cell("sacreds_since_lego")),
            primals_since_lego=self._parse_int(cell("primals_since_lego")),
            primals_since_mythic=self._parse_int(cell("primals_since_mythic")),
            last_ancient_lego_iso=cell("last_ancient_lego_iso"),
            last_void_lego_iso=cell("last_void_lego_iso"),
            last_sacred_lego_iso=cell("last_sacred_lego_iso"),
            last_primal_lego_iso=cell("last_primal_lego_iso"),
            last_primal_mythic_iso=cell("last_primal_mythic_iso"),
            last_updated_iso=cell("last_updated_iso"),
        )
        record.snapshot_name(username)
        return record

    def _new_record(self, header: Sequence[str], discord_id: int, username: str) -> ShardRecord:
        record = ShardRecord(
            header=header,
            discord_id=discord_id,
            username_snapshot=(username or "")[:64],
        )
        record.last_updated_iso = _now_iso()
        return record

    def _matches_user(
        self, row: Sequence[str], header_map: Dict[str, int], discord_id: int
    ) -> bool:
        idx = header_map.get("discord_id", -1)
        if idx < 0 or idx >= len(row):
            return False
        cell = str(row[idx] or "").strip()
        return cell == str(discord_id)

    @staticmethod
    def _normalize(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _parse_int(value: Any) -> int:
        try:
            return int(str(value or "").strip())
        except (TypeError, ValueError):
            return 0


def _config_value(key: str, default: object = None) -> object:
    getter = getattr(runtime_config, "get", None)
    if callable(getter):
        try:
            return getter(key, default)
        except Exception:
            return default
    return getattr(runtime_config, key, default)


def _parse_channel_id(value: object) -> int:
    if value is None:
        return 0
    try:
        text = str(value).strip()
    except Exception:
        return 0
    if not text:
        return 0
    try:
        parsed = int(text)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def _log_config_snapshot(
    *,
    tab_name: str,
    source: str,
    sheet_has_row: bool,
    raw_env: str,
    raw_sheet: str,
    parsed_channel_id: int,
) -> None:
    global _CONFIG_LOG_EMITTED
    if _CONFIG_LOG_EMITTED:
        return

    clean_tab = tab_name or ""
    msg = (
        "🧩 Config — ShardTracker tab=%r source=%s sheet_has_row=%s "
        "raw_env=%r raw_sheet=%r parsed_channel_id=%s"
    )
    log.info(
        msg,
        clean_tab,
        source,
        bool(sheet_has_row),
        raw_env,
        raw_sheet,
        parsed_channel_id,
        extra={
            "tab": clean_tab,
            "source": source,
            "sheet_has_row": bool(sheet_has_row),
            "raw_env": raw_env,
            "raw_sheet": raw_sheet,
            "channel_id": parsed_channel_id,
        },
    )
    _CONFIG_LOG_EMITTED = True


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

