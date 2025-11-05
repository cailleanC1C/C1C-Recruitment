import importlib
import sys

import pytest


_REQUIRED_ENV = {
    "DISCORD_TOKEN": "token",
    "GSPREAD_CREDENTIALS": "{}",
    "RECRUITMENT_SHEET_ID": "sheet",
}


def _load_config(monkeypatch, sheet_config):
    for key, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("ONBOARDING_SHEET_ID", "sheet")

    import shared.sheets.onboarding as onboarding_sheet

    monkeypatch.setattr(
        onboarding_sheet,
        "_load_config",
        lambda force=False: dict(sheet_config),
    )

    sys.modules.pop("shared.config", None)
    try:
        return importlib.import_module("shared.config")
    except Exception:
        sys.modules.pop("shared.config", None)
        raise


def test_onboarding_tab_loaded_from_canonical(monkeypatch):
    cfg = _load_config(monkeypatch, {"onboarding.questions_tab": "Questions"})

    assert cfg.cfg.get("onboarding.questions_tab") == "Questions"
    assert cfg.cfg.get("ONBOARDING_TAB") == "Questions"


def test_onboarding_tab_loaded_from_alias(monkeypatch):
    cfg = _load_config(monkeypatch, {"onboarding_tab": "Legacy"})

    assert cfg.cfg.get("onboarding.questions_tab") == "Legacy"
    assert cfg.cfg.get("ONBOARDING_TAB") == "Legacy"


def test_onboarding_tab_conflict_raises(monkeypatch):
    with pytest.raises(ValueError) as excinfo:
        _load_config(
            monkeypatch,
            {"onboarding.questions_tab": "Primary", "onboarding_tab": "Alias"},
        )

    message = str(excinfo.value)
    assert "onboarding.questions_tab='Primary'" in message
    assert "ONBOARDING_TAB='Alias'" in message


def test_resolve_onboarding_tab_prefers_canonical():
    from shared.config import resolve_onboarding_tab

    mapping = {
        "onboarding.questions_tab": "Canonical",
        "ONBOARDING_TAB": "Canonical",
    }

    assert resolve_onboarding_tab(mapping) == "Canonical"


def test_resolve_onboarding_tab_missing_key():
    from shared.config import resolve_onboarding_tab

    with pytest.raises(KeyError) as excinfo:
        resolve_onboarding_tab({})

    assert "missing config key: onboarding.questions_tab (alias: ONBOARDING_TAB)" in str(
        excinfo.value
    )


def test_resolve_onboarding_tab_conflict():
    from shared.config import resolve_onboarding_tab

    with pytest.raises(ValueError) as excinfo:
        resolve_onboarding_tab(
            {
                "onboarding.questions_tab": "One",
                "ONBOARDING_TAB": "Two",
            }
        )

    message = str(excinfo.value)
    assert "onboarding.questions_tab='One'" in message
    assert "ONBOARDING_TAB='Two'" in message
