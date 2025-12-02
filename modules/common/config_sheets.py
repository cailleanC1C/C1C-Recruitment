from dataclasses import dataclass


@dataclass(frozen=True)
class SheetTarget:
    sheet_id_key: str  # e.g. "RECRUITMENT_SHEET_ID"
    label: str  # human readable name in !config / !checksheet
    context: str  # short identifier, e.g. "recruitment", "onboarding"


# Single source of truth for all Sheets the bot knows about.
SHEET_TARGETS: list[SheetTarget] = [
    SheetTarget("RECRUITMENT_SHEET_ID", "Mirralith / Recruitment Sheet", "recruitment"),
    SheetTarget("ONBOARDING_SHEET_ID", "Onboarding Sheet", "onboarding"),
    SheetTarget("MILESTONES_SHEET_ID", "Milestones Sheet", "milestones"),
    # New: Leagues sheet – once LEAGUES_SHEET_ID is set in env/config,
    # both !config and !checksheet will automatically include it.
    SheetTarget("LEAGUES_SHEET_ID", "Leagues Sheet", "leagues"),
]
