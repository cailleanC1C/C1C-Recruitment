"""Sheet-driven onboarding question schema loader."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Iterable, Literal, Mapping, Sequence, Tuple

from shared.config import cfg, resolve_onboarding_tab
from shared.sheets import onboarding as onboarding_sheets
from shared.sheets.async_core import afetch_records

__all__ = [
    "Question",
    "Option",
    "fetch_question_rows_async",
    "get_questions",
    "register_cache_buckets",
    "schema_hash",
]

log = logging.getLogger(__name__)

_cached_rows_snapshot: Tuple[dict[str, str], ...] | None = None
_cached_questions_by_flow: dict[str, Tuple[Question, ...]] = {}

def _question_tab() -> str:
    """Return the configured onboarding question tab name."""

    return resolve_onboarding_tab(cfg)


@dataclass(frozen=True, slots=True)
class Option:
    """Selectable option with a canonical token value."""

    label: str
    value: str


@dataclass(frozen=True, slots=True)
class Question:
    """Normalized representation of an onboarding question row."""

    flow: Literal["welcome", "promo"]
    order: str
    qid: str
    label: str
    type: str
    required: bool
    maxlen: int | None
    validate: str | None
    help: str | None
    options: tuple[Option, ...]
    multi_max: int | None
    rules: str | None = None


def _sheet_id() -> str:
    return onboarding_sheets._sheet_id()  # type: ignore[attr-defined]


def _normalise_records(records: Iterable[Mapping[str, object]]) -> Tuple[dict[str, str], ...]:
    parsed: list[dict[str, str]] = []
    for record in records:
        normalized: dict[str, str] = {}
        for key, value in record.items():
            key_norm = (key or "").strip().lower()
            if not key_norm:
                continue
            normalized[key_norm] = str(value).strip()
        if normalized:
            parsed.append(normalized)
    return tuple(parsed)


async def fetch_question_rows_async() -> Tuple[dict[str, str], ...]:
    """Fetch and normalise onboarding question rows from Sheets."""

    sheet_id = _sheet_id()
    records = await afetch_records(sheet_id, _question_tab())
    return _normalise_records(records)


def _cached_rows() -> Tuple[dict[str, str], ...]:
    """Return the cached onboarding question rows."""

    global _cached_rows_snapshot, _cached_questions_by_flow

    from shared.sheets.cache_service import cache

    bucket = cache.get_bucket("onboarding_questions")
    if bucket is None:
        _cached_rows_snapshot = None
        _cached_questions_by_flow.clear()
        raise RuntimeError("onboarding_questions cache bucket is not registered")
    value = bucket.value
    if value is None:
        _cached_rows_snapshot = None
        _cached_questions_by_flow.clear()
        raise RuntimeError("onboarding_questions cache is empty (should be preloaded)")
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, Iterable):
        return tuple(dict(row) for row in value)  # defensive copy for iterables
    raise TypeError("unexpected onboarding_questions cache payload")


def _canonicalize_required(value: str | None) -> bool:
    text = (value or "").strip().lower()
    if not text:
        return False
    return text in {"1", "true", "yes", "y", "required"}


def _parse_int(value: str | None) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _normalise_whitespace(text: str | None) -> str | None:
    if text is None:
        return None
    collapsed = " ".join(text.strip().split())
    return collapsed or None


def _canonicalise_option(label: str) -> Option:
    display = label.strip()
    token = "-".join(display.lower().split())
    return Option(label=display, value=token)


def _parse_options(note: str | None) -> tuple[Option, ...]:
    if not note:
        return ()
    pieces = [piece.strip() for piece in note.split(",")]
    values = [piece for piece in pieces if piece]
    return tuple(_canonicalise_option(piece) for piece in values)


def _normalise_type(raw_type: str | None) -> tuple[str, int | None]:
    text = (raw_type or "").strip().lower()
    if not text:
        raise ValueError("Question type is required")
    if text.startswith("multi-select"):
        parts = text.split("-")
        max_count = None
        if len(parts) >= 3:
            try:
                max_count = int(parts[-1])
            except ValueError:
                max_count = None
        return "multi-select", max_count
    return text, None


def _order_sort_key(order: str) -> tuple[int, str]:
    prefix = ""
    suffix = ""
    for idx, char in enumerate(order):
        if not char.isdigit():
            prefix = order[:idx]
            suffix = order[idx:]
            break
    else:
        prefix = order
        suffix = ""
    try:
        prefix_num = int(prefix)
    except ValueError:
        prefix_num = 0
    return prefix_num, suffix


def _build_questions(
    flow: Literal["welcome", "promo"], rows: Sequence[Mapping[str, str]]
) -> list[Question]:
    questions: list[Question] = []
    for row in rows:
        row_flow = row.get("flow")
        if _normalise_whitespace(row_flow) != flow:
            continue
        qid = row.get("qid") or ""
        label = row.get("label") or ""
        order = row.get("order") or ""
        qtype_raw = row.get("type")
        if not qid or not label or not order or not qtype_raw:
            continue
        try:
            qtype, multi_max = _normalise_type(qtype_raw)
        except ValueError:
            log.warning("onboarding question missing type", extra={"qid": qid, "order": order})
            continue
        options = _parse_options(row.get("note")) if qtype in {"single-select", "multi-select"} else ()
        question = Question(
            flow=flow,
            order=order.strip(),
            qid=qid.strip(),
            label=label.strip(),
            type=qtype,
            required=_canonicalize_required(row.get("required")),
            maxlen=_parse_int(row.get("maxlen")),
            validate=_normalise_whitespace(row.get("validate")),
            help=_normalise_whitespace(row.get("help")),
            options=options,
            multi_max=multi_max,
            rules=_normalise_whitespace(row.get("rules")),
        )
        questions.append(question)
    questions.sort(key=lambda q: _order_sort_key(q.order))
    return questions


def get_questions(flow: Literal["welcome", "promo"]) -> list[Question]:
    """Return the parsed onboarding questions for ``flow``."""

    questions = _questions_tuple(flow)
    return list(questions)


def _hash_payload(questions: Iterable[Question]) -> str:
    payload: list[dict[str, object]] = []
    for question in questions:
        payload.append(
            {
                "qid": question.qid,
                "label": question.label,
                "type": question.type,
                "required": question.required,
                "maxlen": question.maxlen,
                "validate": question.validate,
                "help": question.help,
                "options": [(option.value, option.label) for option in question.options],
                "multi_max": question.multi_max,
            }
        )
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


def _questions_tuple(flow: Literal["welcome", "promo"]) -> Tuple[Question, ...]:
    global _cached_rows_snapshot, _cached_questions_by_flow

    rows = _cached_rows()
    if rows is not _cached_rows_snapshot:
        _cached_rows_snapshot = rows
        _cached_questions_by_flow = {
            "welcome": tuple(_build_questions("welcome", rows)),
            "promo": tuple(_build_questions("promo", rows)),
        }
    return _cached_questions_by_flow.get(flow, ())


def schema_hash(flow: Literal["welcome", "promo"]) -> str:
    """Return the stable schema hash for the onboarding question flow."""

    questions = _questions_tuple(flow)
    return _hash_payload(questions)


def register_cache_buckets() -> None:
    """Register cache buckets used by onboarding questions."""

    from shared.sheets.cache_service import register_onboarding_questions_bucket

    register_onboarding_questions_bucket()
