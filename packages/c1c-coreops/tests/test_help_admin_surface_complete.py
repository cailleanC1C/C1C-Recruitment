from __future__ import annotations

import asyncio

from pathlib import Path
import sys


def _ensure_src_on_path() -> None:
    root = Path(__file__).resolve().parents[3]
    src = root / "packages" / "c1c-coreops" / "src"
    root_str = str(root)
    src_str = str(src)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)


_ensure_src_on_path()

from c1c_coreops.cop import HelpSurfaceSection, build_admin_help_surface_async


def _usage_set(section: HelpSurfaceSection) -> set[str]:
    return {entry.usage for entry in section.commands}


def _assert_descriptions(section: HelpSurfaceSection) -> None:
    for entry in section.commands:
        assert isinstance(entry.description, str) and entry.description.strip(), entry.usage


def test_admin_surface_sections_complete() -> None:
    sections = asyncio.run(build_admin_help_surface_async())
    labels = [section.label for section in sections]
    assert labels == [
        "Config & Health",
        "Sheets & Cache",
        "Permissions",
        "Utilities",
        "Welcome Templates",
    ]

    mapping = {section.label: section for section in sections}

    assert _usage_set(mapping["Config & Health"]) == {"!env", "!health"}
    assert _usage_set(mapping["Sheets & Cache"]) == {
        "!checksheet",
        "!config",
        "!refresh",
        "!refresh all",
    }
    assert _usage_set(mapping["Permissions"]) == {
        "!perm",
        "!perm bot allow",
        "!perm bot deny",
        "!perm bot list",
        "!perm bot remove",
        "!perm bot sync",
    }
    assert _usage_set(mapping["Utilities"]) == {"!reload"}
    assert _usage_set(mapping["Welcome Templates"]) == {"!welcome-refresh"}

    for section in sections:
        _assert_descriptions(section)


def test_permissions_commands_sorted() -> None:
    sections = asyncio.run(build_admin_help_surface_async())
    permissions = next(section for section in sections if section.label == "Permissions")
    usages = [entry.usage for entry in permissions.commands]
    assert usages == [
        "!perm",
        "!perm bot allow",
        "!perm bot deny",
        "!perm bot list",
        "!perm bot remove",
        "!perm bot sync",
    ]
