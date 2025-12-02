from __future__ import annotations

import os
from typing import Mapping

from modules.community.leagues.config import LeagueBundle, load_league_bundles
from shared.sheets import config_service


async def load_league_bundles_from_config() -> tuple[str, list[LeagueBundle]]:
    cfg = await config_service.load("leagues")
    if not isinstance(cfg, Mapping):
        raise RuntimeError("config load returned empty payload")

    raw_sheet_id = cfg.get("sheet_id") or os.getenv("LEAGUES_SHEET_ID")
    sheet_id = str(raw_sheet_id or "").strip()
    if not sheet_id:
        raise RuntimeError("LEAGUES_SHEET_ID is missing")

    config_tab = str(cfg.get("tab") or "Config").strip() or "Config"
    bundles = load_league_bundles(sheet_id, config_tab=config_tab)
    return sheet_id, bundles
