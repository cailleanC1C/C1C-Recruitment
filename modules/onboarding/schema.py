from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from shared.config import cfg
from shared.sheets.core import read_table

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

    tab = cfg.get("onboarding.questions_tab")
    if not tab:
        raise RuntimeError("missing config key: onboarding.questions_tab")

    rows = read_table(tab_name=tab)
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


_WELCOME_Q_CACHE: Optional[List[Question]] = None
_WELCOME_Q_LOCK = asyncio.Lock()


async def get_cached_welcome_questions(*, force: bool = False) -> List[Question]:
    """Compatibility shim for legacy async callers expecting cached questions."""

    global _WELCOME_Q_CACHE
    if not force and _WELCOME_Q_CACHE is not None:
        return _WELCOME_Q_CACHE

    async with _WELCOME_Q_LOCK:
        if not force and _WELCOME_Q_CACHE is not None:
            return _WELCOME_Q_CACHE

        data = await asyncio.to_thread(load_welcome_questions)
        _WELCOME_Q_CACHE = data
        return data


def _clear_welcome_questions_cache() -> None:
    """Internal helper to clear the welcome questions cache."""

    global _WELCOME_Q_CACHE
    _WELCOME_Q_CACHE = None

# --------------------------------------------------------------------
# Compatibility shim for legacy controllers
# --------------------------------------------------------------------
def parse_values_list(values):
    """
    Legacy helper referenced by older onboarding controllers.
    Normalizes tuples/lists of strings into a list of non-empty strings.
    """
    if not values:
        return []
    if isinstance(values, (list, tuple)):
        return [str(v).strip() for v in values if v is not None and str(v).strip()]
    return [str(values).strip()]
