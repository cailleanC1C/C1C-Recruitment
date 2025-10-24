"""Environment-driven configuration for CoreOps aliases and bang guards."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Iterable, Tuple

_DEFAULT_ALLOWLIST = (
    "env,reload,health,digest,checksheet,config,help,ping,refresh all"
)


def _env_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    text = value.strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _normalize_tag(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned


def _split_allowlist(raw: str) -> Tuple[str, ...]:
    cleaned = raw.replace("\n", ",").replace(";", ",")
    parts: Iterable[str] = cleaned.split(",")
    seen: set[str] = set()
    normalized: list[str] = []
    for part in parts:
        item = part.strip()
        if not item:
            continue
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(item)
    return tuple(normalized)


@dataclass(frozen=True)
class CoreOpsSettings:
    """Resolved CoreOps configuration derived from environment variables."""

    bot_tag: str | None
    enable_tagged_aliases: bool
    enable_generic_aliases: bool
    admin_bang_allowlist: Tuple[str, ...]

    @property
    def has_tag(self) -> bool:
        return bool(self.bot_tag)

    def describe(self) -> str:
        tag_state = "present" if self.bot_tag else "absent"
        return (
            "tag=%s (%s) tagged_aliases=%s generic_aliases=%s allowlist=%d"
            % (
                self.bot_tag or "(none)",
                tag_state,
                "on" if self.enable_tagged_aliases else "off",
                "on" if self.enable_generic_aliases else "off",
                len(self.admin_bang_allowlist),
            )
        )


def load_coreops_settings() -> CoreOpsSettings:
    """Load CoreOps configuration strictly from the new environment variables."""

    bot_tag = _normalize_tag(os.getenv("BOT_TAG"))
    enable_tagged_aliases = _env_bool(
        os.getenv("COREOPS_ENABLE_TAGGED_ALIASES"),
        default=bool(bot_tag),
    )
    enable_generic_aliases = _env_bool(
        os.getenv("COREOPS_ENABLE_GENERIC_ALIASES"),
        default=False,
    )
    raw_allowlist = os.getenv("COREOPS_ADMIN_BANG_ALLOWLIST", _DEFAULT_ALLOWLIST)
    allowlist = _split_allowlist(raw_allowlist)
    return CoreOpsSettings(
        bot_tag=bot_tag,
        enable_tagged_aliases=enable_tagged_aliases,
        enable_generic_aliases=enable_generic_aliases,
        admin_bang_allowlist=allowlist,
    )


__all__ = ["CoreOpsSettings", "load_coreops_settings"]
