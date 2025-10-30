"""Utility helpers for parsing guardrail rule definitions from markdown."""
from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import List

RULE_PATTERN = re.compile(
    r"^- \*\*(?P<identifier>[A-Z]-\d{2})\s+(?P<title>[^*]+?)\*\*(?::\s*(?P<description>.*))?$"
)
SECTION_PATTERN = re.compile(r"^## +(?P<section>.+)$")


@dataclass(slots=True)
class Rule:
    """Represents a guardrail rule parsed from the specification markdown."""

    identifier: str
    title: str
    section: str
    description: str

def parse_guardrail_rules(path: Path) -> List[Rule]:
    """Parse guardrail rules from the provided markdown file."""

    text = path.read_text(encoding="utf-8")
    rules: List[Rule] = []
    current_section = ""

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        section_match = SECTION_PATTERN.match(line)
        if section_match:
            current_section = section_match.group("section").strip()
            continue

        rule_match = RULE_PATTERN.match(line)
        if not rule_match:
            continue

        identifier = rule_match.group("identifier")
        title = rule_match.group("title").strip()
        description = (rule_match.group("description") or "").strip()
        rules.append(
            Rule(
                identifier=identifier,
                title=title,
                section=current_section,
                description=description,
            )
        )

    return rules


__all__ = ["Rule", "parse_guardrail_rules"]
