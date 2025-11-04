from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from shared.config import (
    get_onboarding_questions_tab,
    get_onboarding_sheet_id,
)
from shared.sheets.core import fetch_records

_ORDER_RE = re.compile(r"^(?P<num>\d+)(?P<tag>[A-Za-z]?)$")


@dataclass
class Question:
    flow: str
    order_raw: str
    order_key: Tuple[int, str]
    qid: str
    label: str
    qtype: str
    required: bool
    maxlen: Optional[int]
    validate: str
    help: str
    note: str
    rules: str


REQUIRED_HEADERS = {
    "flow",
    "order",
    "qid",
    "label",
    "type",
    "required",
    "maxlen",
    "validate",
    "help",
    "note",
    "rules",
}


def _order_key(value: str) -> Tuple[int, str]:
    match = _ORDER_RE.match(str(value).strip())
    if not match:
        return (10 ** 6, "z")
    return (int(match.group("num")), (match.group("tag") or "").lower())


def load_welcome_questions() -> List[Question]:
    """Load and validate the *existing* onboarding tab. Strict, no fallback."""

    tab = get_onboarding_questions_tab()
    if not tab:
        raise RuntimeError(
            "missing config value from get_onboarding_questions_tab()"
        )

    sheet_id = get_onboarding_sheet_id()
    if not sheet_id:
        raise RuntimeError(
            "missing onboarding sheet id from get_onboarding_sheet_id()"
        )

    rows = fetch_records(sheet_id=sheet_id, worksheet=tab)
    if not rows:
        raise RuntimeError(f"tab '{tab}' is empty")

    headers = set(rows[0].keys())
    missing = REQUIRED_HEADERS - headers
    if missing:
        raise RuntimeError(
            f"tab '{tab}' missing required headers: {sorted(missing)}"
        )

    questions: List[Question] = []
    for index, row in enumerate(rows, start=2):
        flow = str(row.get("flow", "")).strip()
        if flow.lower() != "welcome":
            continue

        order_raw = str(row.get("order", "")).strip()
        qid = str(row.get("qid", "")).strip()
        label = str(row.get("label", "")).strip()
        qtype = str(row.get("type", "")).strip()

        question = Question(
            flow=flow,
            order_raw=order_raw,
            order_key=_order_key(order_raw),
            qid=qid,
            label=label,
            qtype=qtype,
            required=str(row.get("required", "")).strip().upper() == "TRUE",
            maxlen=int(row["maxlen"]) if str(row.get("maxlen", "")).strip().isdigit() else None,
            validate=str(row.get("validate", "")).strip(),
            help=str(row.get("help", "")).strip(),
            note=str(row.get("note", "")).strip(),
            rules=str(row.get("rules", "")).strip(),
        )

        if question.qid == "" or question.label == "" or question.qtype == "":
            raise RuntimeError(
                "row {}: qid/label/type required for enabled items (order={!r})".format(
                    index, question.order_raw
                )
            )

        questions.append(question)

    if not questions:
        raise RuntimeError(f"no 'welcome' questions found in tab '{tab}'")

    questions.sort(key=lambda question: question.order_key)
    return questions


_VALUES_PREFIX = re.compile(r"\bvalues\s*:\s*", re.IGNORECASE)


def parse_values_list(spec: str) -> list[str]:
    """Extract a comma-separated option list from a ``validate`` spec."""

    spec = (spec or "").strip()
    if not spec:
        return []
    match = _VALUES_PREFIX.search(spec)
    if not match:
        return []
    body = spec[match.end() :]
    return [part.strip() for part in body.split(",") if part.strip()]
