"""Pytest configuration for shared test fixtures."""

import os


_REQUIRED_ENV_FOR_TESTS = {
    "DISCORD_TOKEN": "test-token",
    "GSPREAD_CREDENTIALS": "{}",
    "RECRUITMENT_SHEET_ID": "test-sheet",
    "COREOPS_ADMIN_BANG_ALLOWLIST": "env,reload,health,digest,checksheet,config,help,ping,refresh,refresh all",
}


for _key, _value in _REQUIRED_ENV_FOR_TESTS.items():
    os.environ.setdefault(_key, _value)
