import importlib
import sys

import pytest


@pytest.mark.parametrize(
    "missing",
    ["DISCORD_TOKEN", "GSPREAD_CREDENTIALS", "RECRUITMENT_SHEET_ID"],
)
def test_missing_required_env_exits(missing, monkeypatch):
    module_name = "shared.config"
    if module_name in sys.modules:
        del sys.modules[module_name]

    monkeypatch.setenv("DISCORD_TOKEN", "token")
    monkeypatch.setenv("GSPREAD_CREDENTIALS", "{}")
    monkeypatch.setenv("RECRUITMENT_SHEET_ID", "sheet")
    monkeypatch.delenv(missing, raising=False)

    with pytest.raises(RuntimeError):
        importlib.import_module(module_name)

    # ensure module removed for next parameter iteration
    if module_name in sys.modules:
        del sys.modules[module_name]
