import importlib
import logging
import os
import sys
from contextlib import contextmanager

import pytest


@contextmanager
def temp_env(**values):
    original = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.mark.usefixtures("caplog")
def test_log_channel_disabled_when_env_missing(caplog):
    caplog.set_level(logging.WARNING)
    module_name = "shared.config"
    original_value = os.environ.get("LOG_CHANNEL_ID")

    with temp_env(
        LOG_CHANNEL_ID=None,
        DISCORD_TOKEN="token",
        GSPREAD_CREDENTIALS="{}",
        RECRUITMENT_SHEET_ID="sheet",
    ):
        if module_name in sys.modules:
            del sys.modules[module_name]
        cfg = importlib.import_module(module_name)
        cfg.reload_config()
        cfg.reload_config()

        warnings = [
            record
            for record in caplog.records
            if "Log channel disabled" in record.getMessage()
        ]
        assert len(warnings) == 1
        assert cfg.get_log_channel_id() is None

    if original_value is None:
        os.environ.pop("LOG_CHANNEL_ID", None)
    else:
        os.environ["LOG_CHANNEL_ID"] = original_value
    importlib.reload(cfg)
