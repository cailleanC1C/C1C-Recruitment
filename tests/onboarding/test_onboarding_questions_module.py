from __future__ import annotations

from shared import config as shared_config
from shared.sheets import onboarding_questions


def test_normalise_records_trims_and_blanks_none() -> None:
    records = (
        {
            " Flow ": " welcome ",
            "Note": None,
            None: "ignored",
            "Spacing": "  keep  ",
        },
    )

    normalised = onboarding_questions._normalise_records(records)

    assert normalised == (
        {
            "flow": "welcome",
            "note": "",
            "spacing": "keep",
        },
    )


def test_describe_source_tails_sheet_id(monkeypatch: "pytest.MonkeyPatch") -> None:
    monkeypatch.setitem(shared_config._CONFIG, "ONBOARDING_SHEET_ID", "sheet-id-abcdef")
    monkeypatch.setitem(shared_config._CONFIG, "ONBOARDING_TAB", "Onboarding")

    metadata = onboarding_questions.describe_source()

    assert metadata["sheet"].startswith("…")
    assert metadata["sheet"].endswith("abcdef")
    assert metadata["tab"] == "Onboarding"
