"""Recruitment sheet ID resolver requirements."""

from __future__ import annotations

import pytest

from shared.sheets import recruitment


def test_sheet_id_requires_explicit_env(monkeypatch: "pytest.MonkeyPatch") -> None:
    monkeypatch.delenv("RECRUITMENT_SHEET_ID", raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        recruitment._sheet_id()

    assert "RECRUITMENT_SHEET_ID" in str(excinfo.value)


def test_sheet_id_returns_value(monkeypatch: "pytest.MonkeyPatch") -> None:
    monkeypatch.setenv("RECRUITMENT_SHEET_ID", "sheet-987654")

    assert recruitment._sheet_id() == "sheet-987654"
    monkeypatch.delenv("RECRUITMENT_SHEET_ID", raising=False)
