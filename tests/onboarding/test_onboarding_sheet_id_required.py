"""Ensure onboarding sheet ID must be configured explicitly."""

from __future__ import annotations

import pytest

from shared.sheets import onboarding


def test_sheet_id_requires_explicit_env(monkeypatch: "pytest.MonkeyPatch") -> None:
    """_sheet_id should raise when ONBOARDING_SHEET_ID is missing."""

    monkeypatch.delenv("ONBOARDING_SHEET_ID", raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        onboarding._sheet_id()

    assert "ONBOARDING_SHEET_ID" in str(excinfo.value)


def test_sheet_id_returns_value_when_present(monkeypatch: "pytest.MonkeyPatch") -> None:
    monkeypatch.setenv("ONBOARDING_SHEET_ID", "abc123")

    assert onboarding._sheet_id() == "abc123"
    # Reset for other tests to avoid residue
    monkeypatch.delenv("ONBOARDING_SHEET_ID", raising=False)
