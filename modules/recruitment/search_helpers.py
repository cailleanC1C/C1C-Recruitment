"""Shared helpers for recruitment search filters and formatting."""

from __future__ import annotations

import re
from typing import Optional, Sequence

__all__ = [
    "parse_spots_num",
    "parse_inactives_num",
    "row_matches",
    "format_filters_footer",
]


# Column indices mirrored from the legacy Matchmaker sheets schema.
COL_B_CLAN = 1
COL_C_TAG = 2
COL_E_SPOTS = 4

COL_P_CB = 15
COL_Q_HYDRA = 16
COL_R_CHIMERA = 17
COL_S_CVC = 18
COL_T_SIEGE = 19
COL_U_STYLE = 20

IDX_AB = 27
IDX_AG_INACTIVES = 32

TOKEN_MAP = {
    "EASY": "ESY",
    "NORMAL": "NML",
    "HARD": "HRD",
    "BRUTAL": "BTL",
    "NM": "NM",
    "UNM": "UNM",
    "ULTRA-NIGHTMARE": "UNM",
    "ULTRANIGHTMARE": "UNM",
}

STYLE_CANON = {
    "STRESS FREE": "STRESSFREE",
    "STRESS-FREE": "STRESSFREE",
    "STRESSFREE": "STRESSFREE",
    "CASUAL": "CASUAL",
    "SEMI COMPETITIVE": "SEMICOMPETITIVE",
    "SEMI-COMPETITIVE": "SEMICOMPETITIVE",
    "SEMICOMPETITIVE": "SEMICOMPETITIVE",
    "COMPETITIVE": "COMPETITIVE",
}


def _norm(value: str) -> str:
    return (value or "").strip().upper()


def _is_header_row(row: Sequence[str]) -> bool:
    clan = _norm(row[COL_B_CLAN]) if len(row) > COL_B_CLAN else ""
    tag = _norm(row[COL_C_TAG]) if len(row) > COL_C_TAG else ""
    spots = _norm(row[COL_E_SPOTS]) if len(row) > COL_E_SPOTS else ""
    return clan in {"CLAN", "CLAN NAME"} or tag == "TAG" or spots == "SPOTS"


def _map_token(choice: str) -> str:
    mapped = TOKEN_MAP.get(_norm(choice))
    return mapped if mapped is not None else _norm(choice)


def _cell_has_diff(cell_text: str, token: str | None) -> bool:
    if not token:
        return True
    mapped = _map_token(token)
    cell = _norm(cell_text)
    if mapped in cell:
        return True
    if mapped == "HRD" and "HARD" in cell:
        return True
    if mapped == "NML" and "NORMAL" in cell:
        return True
    if mapped == "BTL" and "BRUTAL" in cell:
        return True
    if mapped == "UNM":
        if "ULTRA NIGHTMARE" in cell:
            return True
        if "ULTRA-NIGHTMARE" in cell:
            return True
        if "ULTRANIGHTMARE" in cell:
            return True
    return False


def _cell_equals_flag(cell_text: str, expected: Optional[str]) -> bool:
    if expected is None:
        return True
    return (cell_text or "").strip() == expected


def _canon_style(value: str) -> Optional[str]:
    if not value:
        return None
    text = value.replace("-", " ")
    text = " ".join(text.split()).upper()
    if text in STYLE_CANON:
        return STYLE_CANON[text]
    if text == "SEMI COMPETITIVE":
        return "SEMICOMPETITIVE"
    if text == "STRESS FREE":
        return "STRESSFREE"
    return text if text in {"STRESSFREE", "CASUAL", "SEMICOMPETITIVE", "COMPETITIVE"} else None


def _split_styles(cell_text: str) -> set[str]:
    tokens = re.split(r"[,\|/;]+", cell_text or "")
    values: set[str] = set()
    for token in tokens:
        canon = _canon_style(token)
        if canon:
            values.add(canon)
    return values


def _playstyle_ok(cell_text: str, wanted: Optional[str]) -> bool:
    if not wanted:
        return True
    canon = _canon_style(wanted)
    if not canon:
        return True
    return canon in _split_styles(cell_text)


def _parse_number(text: str) -> int:
    match = re.search(r"\d+", text or "")
    return int(match.group()) if match else 0


def parse_spots_num(cell_text: str) -> int:
    """Extract a numeric open-spots count from the sheet cell."""

    return _parse_number(cell_text)


def parse_inactives_num(cell_text: str) -> int:
    """Extract a numeric inactive count from the sheet cell."""

    return _parse_number(cell_text)


def row_matches(
    row: Sequence[str],
    cb: Optional[str],
    hydra: Optional[str],
    chimera: Optional[str],
    cvc: Optional[str],
    siege: Optional[str],
    playstyle: Optional[str],
) -> bool:
    """Return ``True`` if ``row`` satisfies the requested filters."""

    if len(row) <= IDX_AB:
        return False
    if _is_header_row(row):
        return False
    if not (row[COL_B_CLAN] or "").strip():
        return False
    return (
        _cell_has_diff(row[COL_P_CB], cb)
        and _cell_has_diff(row[COL_Q_HYDRA], hydra)
        and _cell_has_diff(row[COL_R_CHIMERA], chimera)
        and _cell_equals_flag(row[COL_S_CVC], cvc)
        and _cell_equals_flag(row[COL_T_SIEGE], siege)
        and _playstyle_ok(row[COL_U_STYLE], playstyle)
    )


def format_filters_footer(
    cb: Optional[str],
    hydra: Optional[str],
    chimera: Optional[str],
    cvc: Optional[str],
    siege: Optional[str],
    playstyle: Optional[str],
    roster_mode: Optional[str] = None,
    *,
    extra_note: str | None = None,
) -> str:
    """Render a human-readable summary of active filters."""

    parts: list[str] = []
    if cb:
        parts.append(f"CB: {cb}")
    if hydra:
        parts.append(f"Hydra: {hydra}")
    if chimera:
        parts.append(f"Chimera: {chimera}")
    if cvc is not None:
        parts.append(f"CvC: {'Yes' if cvc == '1' else 'No'}")
    if siege is not None:
        parts.append(f"Siege: {'Yes' if siege == '1' else 'No'}")
    if playstyle:
        parts.append(f"Playstyle: {playstyle}")

    roster_label = "All"
    if roster_mode == "open":
        roster_label = "Open only"
    elif roster_mode == "full":
        roster_label = "Full only"
    elif roster_mode == "inactives":
        roster_label = "Has inactives"

    if roster_mode is not None:
        parts.append(f"Roster: {roster_label}")

    if extra_note:
        parts.append(extra_note)

    return " • ".join(parts)

