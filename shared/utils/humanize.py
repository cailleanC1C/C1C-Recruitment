"""Formatting helpers for human-friendly durations."""
from __future__ import annotations

from typing import Optional

__all__ = ["humanize_duration"]


def humanize_duration(seconds: Optional[int]) -> str:
    """Return a compact representation of ``seconds`` (fail-soft)."""

    if seconds is None:
        return "-"
    total = max(0, int(seconds))
    units = (("d", 86400), ("h", 3600), ("m", 60), ("s", 1))
    parts: list[str] = []
    for suffix, length in units:
        if total >= length:
            qty, total = divmod(total, length)
            parts.append(f"{qty}{suffix}")
        if len(parts) == 2:
            break
    if not parts:
        parts.append("0s")
    return "".join(parts)
