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


def test_normalise_type_maps_boolean_aliases() -> None:
    aliases = [
        "Boolean",
        "bool",
        "BOOL (Yes/No)",
        "Yes/No",
        "yes - no",
        "yes_no",
        "Y/N",
        "TrueFalse",
        "true/false",
    ]

    for alias in aliases:
        normalised, max_count = onboarding_questions._normalise_type(alias)
        assert normalised == "bool"
        assert max_count is None


def _option_pairs(options: tuple[onboarding_questions.Option, ...]) -> list[tuple[str, str]]:
    return [(option.label, option.value) for option in options]


def test_parse_options_supports_numeric_range() -> None:
    options = onboarding_questions._parse_options("1-5")

    assert _option_pairs(options) == [
        ("1", "1"),
        ("2", "2"),
        ("3", "3"),
        ("4", "4"),
        ("5", "5"),
    ]


def test_parse_options_supports_en_dash_range() -> None:
    options = onboarding_questions._parse_options("1 – 3")

    assert _option_pairs(options) == [
        ("1", "1"),
        ("2", "2"),
        ("3", "3"),
    ]


def test_parse_options_supports_whitespace_separated_numbers() -> None:
    options = onboarding_questions._parse_options("1 2 3 4 5")

    assert _option_pairs(options) == [
        ("1", "1"),
        ("2", "2"),
        ("3", "3"),
        ("4", "4"),
        ("5", "5"),
    ]


def test_parse_options_supports_compact_digits() -> None:
    options = onboarding_questions._parse_options("12345")

    assert _option_pairs(options) == [
        ("1", "1"),
        ("2", "2"),
        ("3", "3"),
        ("4", "4"),
        ("5", "5"),
    ]
