import pytest

from shared.config import resolve_onboarding_tab


def test_resolve_onboarding_tab_returns_value() -> None:
    mapping = {"ONBOARDING_TAB": "Questions"}

    assert resolve_onboarding_tab(mapping) == "Questions"


def test_resolve_onboarding_tab_missing_key() -> None:
    with pytest.raises(KeyError) as excinfo:
        resolve_onboarding_tab({})

    assert excinfo.value.args[0] == "missing config key: ONBOARDING_TAB"
