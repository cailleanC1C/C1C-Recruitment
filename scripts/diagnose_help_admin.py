#!/usr/bin/env python3
"""Generate Help diagnostics for CoreOps admin commands."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import c1c_coreops.cog as coreops_cog

AUDIT_DIR = Path("AUDIT")
REGISTRY_PATH = AUDIT_DIR / ".runtime_help_registry.json"
ADMIN_LINES_PATH = AUDIT_DIR / ".runtime_help_admin_lines.txt"
OUTPUT_PATH = AUDIT_DIR / "Help-Admin-Diagnosis.md"

EXPECTED_CANONICAL = (
    "checksheet",
    "config",
    "digest",
    "env",
    "health",
    "ping",
    "refresh",
    "refresh all",
    "reload",
)


@dataclass
class RegistryEntry:
    name: str
    category: str
    aliases: Sequence[str]
    rbac: str
    module: str

    @classmethod
    def from_json(cls, payload: dict[str, object]) -> "RegistryEntry":
        return cls(
            name=str(payload.get("name", "")),
            category=str(payload.get("category", "")),
            aliases=tuple(str(alias) for alias in payload.get("aliases", []) or []),
            rbac=str(payload.get("rbac", "")),
            module=str(payload.get("module", "")),
        )


def _read_registry() -> list[RegistryEntry]:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Missing registry snapshot: {REGISTRY_PATH}")

    entries: list[RegistryEntry] = []
    with REGISTRY_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            entries.append(RegistryEntry.from_json(payload))
    return entries


def _read_admin_lines() -> list[str]:
    if not ADMIN_LINES_PATH.exists():
        raise FileNotFoundError(f"Missing help lines snapshot: {ADMIN_LINES_PATH}")

    with ADMIN_LINES_PATH.open("r", encoding="utf-8") as handle:
        return [line.rstrip("\n") for line in handle if line.strip()]


def _allowlist_size(value: str) -> int:
    if not value:
        return 0
    parts = [segment.strip() for segment in value.replace(";", ",").split(",")]
    return len([segment for segment in parts if segment])


def _format_aliases(aliases: Sequence[str], bot_tag: str) -> str:
    if not aliases:
        return "—"

    formatted: list[str] = []
    lowered_tag = bot_tag.lower()
    for alias in aliases:
        label = alias
        if lowered_tag and alias.lower().startswith(lowered_tag):
            label = f"{alias} (tagged)"
        formatted.append(label)
    return "<br>".join(formatted)


def _extract_usage(line: str) -> str:
    start = line.find("`")
    if start == -1:
        return ""
    end = line.find("`", start + 1)
    if end == -1:
        return ""
    return line[start + 1 : end]


def _classify_usages(usages: Iterable[str], bot_tag: str) -> tuple[set[str], set[str]]:
    bare: set[str] = set()
    tagged: set[str] = set()
    normalized_tag = bot_tag.lower()
    tag_prefix = f"!{normalized_tag}" if normalized_tag else ""

    for usage in usages:
        value = usage.strip()
        if not value.startswith("!"):
            continue
        lowered = value.lower()
        if normalized_tag and lowered.startswith(tag_prefix):
            tagged.add(value)
        else:
            bare.add(value)
    return bare, tagged


def _format_table(entries: Sequence[RegistryEntry], bot_tag: str) -> str:
    header = "| Command | Category | Aliases | RBAC | Source |\n| --- | --- | --- | --- | --- |"
    rows = []
    for entry in entries:
        alias_text = _format_aliases(entry.aliases, bot_tag)
        row = f"| `{entry.name}` | {entry.category or '—'} | {alias_text} | {entry.rbac or '—'} | `{entry.module or '—'}` |"
        rows.append(row)
    return "\n".join([header, *rows])


def _format_lines_table(lines: Sequence[str]) -> str:
    header = "| Line |\n| --- |"
    rows: list[str] = []
    for line in lines:
        escaped = line.replace("|", "\\|")
        rows.append(f"| {escaped} |")
    return "\n".join([header, *rows])


def _render_diff_block(bare_gap: set[str], tagged_gap: set[str]) -> str:
    bare_display = ", ".join(sorted(bare_gap)) or "∅"
    tagged_display = ", ".join(sorted(tagged_gap)) or "∅"
    return "\n".join(
        [
            "```diff",
            f"- expected_bare_set - rendered_bare_set: {bare_display}",
            f"- expected_tagged_set - rendered_tagged_set: {tagged_display}",
            "```",
        ]
    )


def _root_cause_paragraph(bot_tag: str, generic_enabled: str) -> str:
    settings_line = _lookup_source_line(coreops_cog.CoreOpsCog._apply_generic_alias_policy)
    help_line = _lookup_source_line(coreops_cog.CoreOpsCog._emit_help_registry_debug_snapshot)
    toggle_state = "enabled" if generic_enabled == "1" else "disabled"
    return (
        "CoreOps only lists aliases that survive `CoreOpsCog._apply_generic_alias_policy`"
        f" (source: {settings_line}). With `COREOPS_ENABLE_GENERIC_ALIASES={generic_enabled}` ({toggle_state}),"
        " bare admin commands are removed from `__cog_commands__`, so the help builder never sees"
        " `!env`, `!config`, and peers. Tagged variants remain because the `rec` group stays registered"
        f" while ping’s generic command persists outside the admin gate (see {help_line})."
    )


def _lookup_source_line(obj) -> str:
    import inspect

    try:
        source_file = inspect.getsourcefile(obj)
        _, start_line = inspect.getsourcelines(obj)
    except Exception:
        return "unknown"
    path = Path(source_file).resolve()
    try:
        relative = path.relative_to(Path.cwd())
    except ValueError:
        relative = path
    return f"{relative}:{start_line}"


def main() -> int:
    bot_tag = os.getenv("BOT_TAG", "")
    tagged_toggle = os.getenv("COREOPS_ENABLE_TAGGED_ALIASES", "")
    generic_toggle = os.getenv("COREOPS_ENABLE_GENERIC_ALIASES", "")
    allowlist = os.getenv("COREOPS_ADMIN_BANG_ALLOWLIST", "")

    registry_entries = sorted(_read_registry(), key=lambda item: item.name)
    admin_lines = _read_admin_lines()

    usages = [_extract_usage(line) for line in admin_lines]
    bare_rendered, tagged_rendered = _classify_usages(usages, bot_tag)

    expected_bare = {f"!{name}" for name in EXPECTED_CANONICAL}
    expected_tagged = {f"!{bot_tag} {name}" for name in EXPECTED_CANONICAL} if bot_tag else set()

    bare_gap = expected_bare - bare_rendered
    tagged_gap = expected_tagged - tagged_rendered

    env_section = "\n".join(
        [
            "## Environment",
            f"- `BOT_TAG`: `{bot_tag or '∅'}`",
            f"- `COREOPS_ENABLE_TAGGED_ALIASES`: `{tagged_toggle or '∅'}`",
            f"- `COREOPS_ENABLE_GENERIC_ALIASES`: `{generic_toggle or '∅'}`",
            f"- `COREOPS_ADMIN_BANG_ALLOWLIST` size: `{_allowlist_size(allowlist)}`",
        ]
    )

    registry_table = "\n".join(
        ["## Registered CoreOps Commands", _format_table(registry_entries, bot_tag)]
    )

    help_table = "\n".join(["## Help Rendered Admin Lines", _format_lines_table(admin_lines)])

    diff_block = "\n".join(["## Missing Aliases", _render_diff_block(bare_gap, tagged_gap)])

    root_cause = "\n".join(["## Root Cause", _root_cause_paragraph(bot_tag, generic_toggle)])

    report = "\n\n".join([env_section, registry_table, help_table, diff_block, root_cause]) + "\n"
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
