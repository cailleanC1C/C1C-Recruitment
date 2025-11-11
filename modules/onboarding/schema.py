from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from shared.cache import telemetry as cache_telemetry

from shared.sheets import onboarding_questions
from modules.onboarding.rules import validate_rules

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
    options: Tuple[str, ...]
    visibility_rules: str
    nav_rules: str


def _order_key(value: str) -> Tuple[int, str]:
    match = _ORDER_RE.match(str(value).strip())
    if not match:
        return (10 ** 6, "z")
    return (int(match.group("num")), (match.group("tag") or "").lower())


def _to_schema_question(raw: onboarding_questions.Question) -> Question:
    note = ",".join(option.label for option in raw.options)
    return Question(
        flow=raw.flow,
        order_raw=raw.order,
        order_key=_order_key(raw.order),
        qid=raw.qid,
        label=raw.label,
        qtype=raw.type,
        required=bool(raw.required),
        maxlen=raw.maxlen,
        validate=(raw.validate or ""),
        help=(raw.help or ""),
        note=note,
        rules=(raw.rules or ""),
        options=tuple(option.value for option in raw.options),
        visibility_rules=(raw.visibility_rules or ""),
        nav_rules=(raw.nav_rules or ""),
    )


def load_welcome_questions() -> List[Question]:
    """Load and validate the onboarding tab via the shared cache."""

    _, tab = onboarding_questions.resolve_source()
    rows = onboarding_questions.get_questions("welcome")
    if not rows:
        raise RuntimeError(
            f"onboarding_questions cache empty after refresh; tab='{tab}'"
        )

    rule_errors = validate_rules(rows)
    if rule_errors:
        joined = "; ".join(rule_errors)
        raise ValueError(f"Invalid onboarding rules: {joined}")

    questions = [_to_schema_question(question) for question in rows]
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

        onboarding_questions.register_cache_buckets()
        if force:
            try:
                await cache_telemetry.refresh_now(
                    name="onboarding_questions", actor="schema"
                )
            except Exception:
                pass
            _WELCOME_Q_CACHE = None
        else:
            try:
                if onboarding_questions.cached_rows() is None:
                    await cache_telemetry.refresh_now(
                        name="onboarding_questions", actor="schema"
                    )
            except Exception:
                # non-fatal: fall through to loader which will raise if still empty
                pass

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
