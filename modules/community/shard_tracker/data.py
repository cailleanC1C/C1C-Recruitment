"""Sheet access helpers for the Shard & Mercy tracker."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence

from shared.config import get_milestones_sheet_id
from shared.sheets import async_core

log = logging.getLogger("c1c.shards.data")

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
            if not sheet_id:
                raise ShardTrackerConfigError("MILESTONES_SHEET_ID missing")

            config_tab = os.getenv("MILESTONES_CONFIG_TAB", "Config").strip() or "Config"
            rows = await async_core.afetch_records(sheet_id, config_tab)
            config_map = self._parse_config(rows)
            tab_name = config_map.get("shard_mercy_tab")
            if not tab_name:
                raise ShardTrackerConfigError("SHARD_MERCY_TAB missing in milestones Config tab")
            raw_channel = config_map.get("shard_mercy_channel_id")
            channel_id = self._parse_int(raw_channel)
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

    def _parse_config(self, rows: Sequence[Dict[str, Any]]) -> Dict[str, str]:
        config: Dict[str, str] = {}
        for row in rows:
            key = self._normalize(row.get("key"))
            value = (str(row.get("value", "")).strip())
            if key:
                config[key] = value
        return config

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


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

