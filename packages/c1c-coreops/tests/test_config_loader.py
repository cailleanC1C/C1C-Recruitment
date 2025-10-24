from __future__ import annotations

import pytest

from c1c_coreops.config import load_coreops_settings


@pytest.fixture(autouse=True)
def clear_coreops_env(monkeypatch):
    for key in [
        "BOT_TAG",
        "COREOPS_ENABLE_TAGGED_ALIASES",
        "COREOPS_ENABLE_GENERIC_ALIASES",
        "COREOPS_ADMIN_BANG_ALLOWLIST",
    ]:
        monkeypatch.delenv(key, raising=False)
    yield


def test_defaults_without_tag():
    settings = load_coreops_settings()
    assert settings.bot_tag is None
    assert settings.enable_tagged_aliases is False
    assert settings.enable_generic_aliases is False
    assert settings.admin_bang_allowlist == (
        "env",
        "reload",
        "health",
        "digest",
        "checksheet",
        "config",
        "help",
        "ping",
        "refresh all",
    )


def test_tag_enables_tagged_aliases(monkeypatch):
    monkeypatch.setenv("BOT_TAG", "rec")
    settings = load_coreops_settings()
    assert settings.bot_tag == "rec"
    assert settings.enable_tagged_aliases is True


def test_tag_toggle_respects_override(monkeypatch):
    monkeypatch.setenv("BOT_TAG", "rec")
    monkeypatch.setenv("COREOPS_ENABLE_TAGGED_ALIASES", "0")
    settings = load_coreops_settings()
    assert settings.enable_tagged_aliases is False


def test_generic_alias_flag(monkeypatch):
    monkeypatch.setenv("COREOPS_ENABLE_GENERIC_ALIASES", "1")
    settings = load_coreops_settings()
    assert settings.enable_generic_aliases is True


def test_custom_allowlist(monkeypatch):
    monkeypatch.setenv("COREOPS_ADMIN_BANG_ALLOWLIST", "env, refresh all ,\nhealth")
    settings = load_coreops_settings()
    assert settings.admin_bang_allowlist == ("env", "refresh all", "health")
