import pytest

from modules.community.leagues import config as leagues_config


def _build_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = [
        {"SPEC_KEY": "LEAGUE_LEGENDARY_HEADER", "SHEET_NAME": "Legendary", "RANGE": "A1:B2"},
        {"SPEC_KEY": "LEAGUE_RISING_HEADER", "SHEET_NAME": "Rising Stars", "RANGE": "A1:B2"},
        {"SPEC_KEY": "LEAGUE_STORM_HEADER", "SHEET_NAME": "Stormforged", "RANGE": "A1:B2"},
    ]
    for index in range(1, 10):
        rows.append(
            {
                "SPEC_KEY": f"LEAGUE_LEGENDARY_{index}",
                "SHEET_NAME": "Legendary",
                "RANGE": f"A{index}:B{index}",
            }
        )
    for index in range(1, 8):
        rows.append(
            {
                "SPEC_KEY": f"LEAGUE_RISING_{index}",
                "SHEET_NAME": "Rising Stars",
                "RANGE": f"A{index}:B{index}",
            }
        )
    for index in range(1, 5):
        rows.append(
            {
                "SPEC_KEY": f"LEAGUE_STORM_{index}",
                "SHEET_NAME": "Stormforged",
                "RANGE": f"A{index}:B{index}",
            }
        )
    return rows


def test_load_league_bundles_groups_specs(monkeypatch):
    rows = _build_rows()
    monkeypatch.setattr(leagues_config.sheets_core, "fetch_records", lambda *_args, **_kwargs: rows)

    bundles = leagues_config.load_league_bundles("dummy-sheet")
    assert {bundle.slug for bundle in bundles} == {"legendary", "rising", "storm"}

    legendary = next(bundle for bundle in bundles if bundle.slug == "legendary")
    assert legendary.header.sheet_name == "Legendary"
    assert len(legendary.boards) == 9
    assert legendary.boards[0].key == "LEAGUE_LEGENDARY_1"
    assert legendary.boards[-1].key == "LEAGUE_LEGENDARY_9"

    rising = next(bundle for bundle in bundles if bundle.slug == "rising")
    assert len(rising.boards) == 7
    assert rising.boards[0].cell_range == "A1:B1"

    storm = next(bundle for bundle in bundles if bundle.slug == "storm")
    assert len(storm.boards) == 4
    assert storm.boards[-1].cell_range == "A4:B4"


def test_load_league_bundles_filters_disabled(monkeypatch):
    rows = _build_rows()
    rows.append(
        {
            "SPEC_KEY": "LEAGUE_LEGENDARY_10",
            "SHEET_NAME": "Legendary",
            "RANGE": "A10:B10",
            "ENABLED": "false",
        }
    )
    monkeypatch.setattr(leagues_config.sheets_core, "fetch_records", lambda *_args, **_kwargs: rows)

    bundles = leagues_config.load_league_bundles("dummy-sheet")
    legendary = next(bundle for bundle in bundles if bundle.slug == "legendary")
    assert len(legendary.boards) == 9
    assert all(spec.key != "LEAGUE_LEGENDARY_10" for spec in legendary.boards)


def test_load_league_bundles_missing_header(monkeypatch):
    rows = [
        {"SPEC_KEY": "LEAGUE_LEGENDARY_1", "SHEET_NAME": "Legendary", "RANGE": "A1"},
    ]
    monkeypatch.setattr(leagues_config.sheets_core, "fetch_records", lambda *_args, **_kwargs: rows)

    with pytest.raises(leagues_config.LeaguesConfigError):
        leagues_config.load_league_bundles("dummy-sheet")
