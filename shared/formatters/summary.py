"""Helpers for building recruitment summary strings."""

from __future__ import annotations

import math
from typing import Any

__all__ = [
    "abbr_number",
    "cvc_priority",
    "inline_merge",
    "is_hide_value",
]

_HIDE_TOKENS = {"", "0", "no", "none", "dunno"}
_PRIORITY_MAP = {
    "1": "Low",
    "2": "Low-Medium",
    "3": "Medium",
    "4": "High-Medium",
    "5": "High",
}


def _strip(value: str | None) -> str:
    return value.strip() if value is not None else ""


def _normalise_number_token(token: str) -> str:
    text = token.replace(",", "").replace(" ", "")
    return text


def _parse_numeric(value: Any) -> tuple[float | None, str]:
    if value is None:
        return None, ""
    if isinstance(value, (int, float)):
        return float(value), str(value)
    text = _strip(str(value))
    if not text:
        return None, ""
    normalized = _normalise_number_token(text).lower()
    multiplier = 1.0
    if normalized.endswith("k"):
        multiplier = 1_000.0
        normalized = normalized[:-1]
    elif normalized.endswith("m"):
        multiplier = 1_000_000.0
        normalized = normalized[:-1]
    try:
        numeric = float(normalized)
    except (TypeError, ValueError):
        return None, text
    return numeric * multiplier, text


def abbr_number(value: Any) -> str:
    """Return a compact representation of ``value`` with K/M suffixes."""

    numeric, original = _parse_numeric(value)
    if numeric is None:
        return original
    absolute = abs(numeric)
    if absolute < 1_000:
        return original or str(int(numeric))
    if absolute < 1_000_000:
        rounded = math.floor((numeric / 1_000) + 0.5)
        return f"{int(rounded)} K"
    compact = numeric / 1_000_000
    rounded = math.floor(compact * 10 + 0.5) / 10
    formatted = f"{rounded:.1f}".rstrip("0").rstrip(".")
    return f"{formatted} M"


def cvc_priority(value: Any) -> str:
    """Return the CvC priority label for ``value``."""

    if value is None:
        return ""

    key: str | None
    if isinstance(value, dict):
        label = value.get("label") or value.get("value")
        if isinstance(label, str):
            key = label.strip()
        elif label is not None:
            key = str(label).strip()
        else:
            key = str(value).strip()
    else:
        key = str(value).strip()

    if not key:
        return ""
    return _PRIORITY_MAP.get(key, key)


def is_hide_value(value: Any) -> bool:
    """Return ``True`` when the value represents an empty/hidden token."""

    if value is None:
        return True
    if isinstance(value, str):
        token = value.strip().lower()
    elif isinstance(value, (int, float)):
        if value == 0:
            return True
        token = str(value).strip().lower()
    else:
        token = str(value).strip().lower()
    return token in _HIDE_TOKENS


def inline_merge(
    a_label: str | None,
    a_value: str | None,
    b_label: str | None,
    b_value: str | None,
) -> str:
    """Return an inline string combining two label/value pairs."""

    parts: list[str] = []
    if a_value:
        segment = f"**{a_label}:** {a_value}" if a_label else a_value
        parts.append(segment)
    if b_value:
        segment = f"**{b_label}:** {b_value}" if b_label else b_value
        parts.append(segment)
    return " • ".join(parts)
