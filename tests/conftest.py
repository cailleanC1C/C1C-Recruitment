"""Pytest configuration for shared test fixtures."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_project_root_on_path(source_file: Path) -> None:
    """Add the repository root to ``sys.path`` when running from subpackages."""

    for candidate in [source_file.parent, *source_file.parents]:
        shared_dir = candidate / "shared"
        if shared_dir.is_dir():
            project_root = str(candidate)
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            break


_ensure_project_root_on_path(Path(__file__).resolve())

from shared.testing import apply_required_test_environment

apply_required_test_environment()
