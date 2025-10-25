"""Utilities for seeding environment variables required by the test suite."""

from __future__ import annotations

import os


_REQUIRED_ENV_FOR_TESTS = {
    "DISCORD_TOKEN": "test-token",
    "GSPREAD_CREDENTIALS": "{}",
    "RECRUITMENT_SHEET_ID": "test-sheet",
    "COREOPS_ADMIN_BANG_ALLOWLIST": (
        "env,reload,health,digest,checksheet,config,help,ping,refresh,refresh all"
    ),
}


def apply_required_test_environment() -> None:
    """Populate the minimum environment expected by the test suite."""

    for key, value in _REQUIRED_ENV_FOR_TESTS.items():
        os.environ.setdefault(key, value)
