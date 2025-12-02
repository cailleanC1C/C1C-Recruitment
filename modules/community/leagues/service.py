from __future__ import annotations

from typing import Mapping

from modules.community.leagues.config import (
    LeagueBundle,
    load_league_bundles_from_rows,
)
from shared.sheets import config_service


async def load_league_bundles_from_config() -> tuple[str, list[LeagueBundle]]:
    cfg = await config_service.load("leagues")
    if not isinstance(cfg, Mapping):
        raise RuntimeError("config load returned empty payload")

    sheet_id = str(cfg.get("sheet_id") or "").strip()
    if not sheet_id:
        raise RuntimeError("LEAGUES_SHEET_ID is missing")

    config_map = cfg.get("config")
    rows: list[Mapping[str, object]] = []
    if isinstance(config_map, Mapping):
        rows.extend(
            dict(value)
            for value in config_map.values()
            if isinstance(value, Mapping)
        )

    bundles = load_league_bundles_from_rows(rows)
    return sheet_id, bundles
