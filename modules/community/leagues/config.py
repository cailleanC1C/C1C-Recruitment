from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Mapping

from shared.sheets import core as sheets_core


class LeaguesConfigError(RuntimeError):
    """Raised when the Leagues Config tab is missing required specs."""


@dataclass(frozen=True)
class LeagueSpec:
    key: str
    sheet_name: str
    cell_range: str


@dataclass(frozen=True)
class LeagueBundle:
    slug: str
    display_name: str
    expected_boards: int
    header: LeagueSpec
    boards: list[LeagueSpec]


_LEAGUE_MAP: dict[str, tuple[str, int]] = {
    "legendary": ("Legendary League", 9),
    "rising": ("Rising Stars League", 7),
    "storm": ("Stormforged League", 4),
}


def _normalize(text: str | None) -> str:
    return (text or "").strip()


def _iter_league_rows(sheet_id: str, config_tab: str) -> Iterator[Mapping[str, object]]:
    records = sheets_core.fetch_records(sheet_id, config_tab)
    yield from records or []


def _parse_bool(value: str | object | None) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return True


def _extract_field(row: Mapping[str, object], *candidates: str) -> str:
    for name in candidates:
        key = name.strip().lower()
        for column, value in row.items():
            if (column or "").strip().lower() == key:
                return _normalize(str(value))
    return ""


def _iter_league_specs(rows: Iterable[Mapping[str, object]]) -> Iterator[LeagueSpec]:
    for row in rows:
        spec_key = _extract_field(row, "spec_key", "key")
        sheet_name = _extract_field(row, "sheet_name", "sheet", "tab")
        cell_range = _extract_field(row, "range", "cell_range")
        enabled = _parse_bool(_extract_field(row, "enabled", "active"))

        if not enabled:
            continue
        if not spec_key or not sheet_name or not cell_range:
            continue

        normalized_key = spec_key.strip()
        if not normalized_key.upper().startswith("LEAGUE_"):
            continue

        yield LeagueSpec(
            key=normalized_key,
            sheet_name=sheet_name,
            cell_range=cell_range,
        )


def _split_suffix(key: str, prefix: str) -> int | None:
    remainder = key[len(prefix) :]
    try:
        return int(remainder)
    except (TypeError, ValueError):
        return None


def _bundle_for_slug(specs: list[LeagueSpec], slug: str) -> LeagueBundle | None:
    display_name, expected = _LEAGUE_MAP[slug]
    prefix = f"LEAGUE_{slug.upper()}_"
    header_key = f"{prefix}HEADER"
    header = next((spec for spec in specs if spec.key.upper() == header_key), None)

    boards: list[LeagueSpec] = []
    for spec in specs:
        upper_key = spec.key.upper()
        if not upper_key.startswith(prefix):
            continue
        suffix = upper_key[len(prefix) :]
        if suffix == "HEADER":
            continue
        index = _split_suffix(upper_key, prefix)
        if index is None:
            continue
        boards.append(spec)

    boards.sort(key=lambda item: _split_suffix(item.key.upper(), prefix) or 0)

    if header is None:
        return None

    return LeagueBundle(
        slug=slug,
        display_name=display_name,
        expected_boards=expected,
        header=header,
        boards=boards,
    )


def load_league_bundles(sheet_id: str, *, config_tab: str = "Config") -> list[LeagueBundle]:
    rows = list(_iter_league_rows(sheet_id, config_tab))
    specs = list(_iter_league_specs(rows))

    bundles: list[LeagueBundle] = []
    missing: list[str] = []

    for slug in ("legendary", "rising", "storm"):
        bundle = _bundle_for_slug(specs, slug)
        if bundle is None:
            missing.append(slug)
            continue
        bundles.append(bundle)

    if missing:
        missing_labels = ", ".join(missing)
        raise LeaguesConfigError(f"config missing headers for: {missing_labels}")

    return bundles
