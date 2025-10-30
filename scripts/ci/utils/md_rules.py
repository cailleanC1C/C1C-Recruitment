"""Utility helpers for parsing guardrail rule definitions from markdown."""
from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import List

RULE_PATTERN = re.compile(r"^- \*\*(?P<body>.+?)\*\*(?P<rest>.*)$")
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

        body = rule_match.group("body").strip()
        rest = rule_match.group("rest").lstrip()

        if not body:
            continue

        body_parts = body.split(None, 1)
        identifier = body_parts[0]
        title = body_parts[1] if len(body_parts) > 1 else ""

        if not re.fullmatch(r"[A-Z]-\d{2}", identifier):
            continue

        # Titles may include a trailing colon inside the bold block.
        if title.endswith(":"):
            title = title[:-1].rstrip()

        title = title.strip()

        # Descriptions can begin with a colon directly after the bold block.
        if rest.startswith(":"):
            rest = rest[1:].lstrip()

        description = rest

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
