"""Environment-driven configuration for CoreOps command routing."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Iterable

__all__ = [
    "DEFAULT_ADMIN_BANG_ALLOWLIST",
    "CoreOpsSettings",
    "build_command_variants",
    "build_lookup_sequence",
    "load_coreops_settings",
    "normalize_command_text",
]

DEFAULT_ADMIN_BANG_ALLOWLIST = "env,reload,health,digest,checksheet,config,help,ping,refresh all"


@dataclass(frozen=True)
class CoreOpsSettings:
    """Resolved CoreOps configuration derived from environment variables."""

    bot_tag: str
    enable_tagged_aliases: bool
    enable_generic_aliases: bool
    admin_bang_allowlist: tuple[str, ...]
    admin_bang_base_commands: tuple[str, ...]

    def describe(self) -> dict[str, object]:
        """Return a serializable summary for logging."""

        return {
            "bot_tag": self.bot_tag,
            "tagged_aliases": self.enable_tagged_aliases,
            "generic_aliases": self.enable_generic_aliases,
            "admin_bang_allowlist": list(self.admin_bang_allowlist),
        }


def load_coreops_settings() -> CoreOpsSettings:
    """Load CoreOps settings from the current process environment."""

    bot_tag = _normalize_tag(os.getenv("BOT_TAG", ""))

    enable_tagged_aliases = _coerce_bool(
        os.getenv("COREOPS_ENABLE_TAGGED_ALIASES"),
        default=bool(bot_tag),
    )
    enable_generic_aliases = _coerce_bool(
        os.getenv("COREOPS_ENABLE_GENERIC_ALIASES"),
        default=False,
    )

    allowlist_raw = os.getenv(
        "COREOPS_ADMIN_BANG_ALLOWLIST", DEFAULT_ADMIN_BANG_ALLOWLIST
    )
    allowlist = _parse_allowlist(allowlist_raw)
    base_commands = _derive_base_commands(allowlist)

    return CoreOpsSettings(
        bot_tag=bot_tag,
        enable_tagged_aliases=enable_tagged_aliases,
        enable_generic_aliases=enable_generic_aliases,
        admin_bang_allowlist=allowlist,
        admin_bang_base_commands=base_commands,
    )


def normalize_command_text(command: str) -> str:
    """Normalize a command string for comparison."""

    return " ".join(str(command or "").split()).strip().lower()


def build_command_variants(
    settings: CoreOpsSettings, command_path: str
) -> tuple[str, ...]:
    """Return possible command lookups for a CoreOps admin invocation."""

    cleaned = _normalize_command_path(command_path)
    if not cleaned:
        return tuple()

    variants: list[str] = [cleaned]
    if settings.enable_tagged_aliases and settings.bot_tag:
        tagged = f"{settings.bot_tag} {cleaned}".strip()
        if tagged and tagged not in variants:
            variants.append(tagged)

    legacy = f"rec {cleaned}".strip()
    if legacy and legacy not in variants:
        variants.append(legacy)

    return tuple(variants)


def build_lookup_sequence(base: str, remainder: str | None) -> tuple[str, ...]:
    """Return lookup candidates for resolving a CoreOps admin command."""

    base_name = normalize_command_text(base)
    candidates: list[str] = []
    if base_name:
        candidates.append(base_name)

    if remainder:
        full = normalize_command_text(f"{base} {remainder}")
        if full and full not in candidates:
            candidates.append(full)

    return tuple(candidates)


def _coerce_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None:
        return default
    text = raw.strip().lower()
    if not text:
        return default
    return text in {"1", "true", "t", "yes", "y", "on"}


def _normalize_tag(raw: str) -> str:
    text = "".join(ch for ch in raw.strip().lower() if ch.isalnum() or ch in {"-", "_"})
    return text


def _parse_allowlist(raw: str) -> tuple[str, ...]:
    items: list[str] = []
    seen: set[str] = set()
    for chunk in raw.split(","):
        cleaned = normalize_command_text(chunk)
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        items.append(cleaned)
    if not items:
        return _parse_allowlist(DEFAULT_ADMIN_BANG_ALLOWLIST)
    return tuple(items)


def _derive_base_commands(entries: Iterable[str]) -> tuple[str, ...]:
    bases: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        base = entry.split(" ", 1)[0].strip()
        if not base:
            continue
        if base in seen:
            continue
        seen.add(base)
        bases.append(base)
    return tuple(bases)


def _normalize_command_path(value: str) -> str:
    return " ".join(str(value or "").split()).strip()
