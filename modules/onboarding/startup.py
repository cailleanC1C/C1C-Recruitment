"""Background tasks for onboarding feature startup."""

from __future__ import annotations

import asyncio

from modules.common.logs import log
from modules.onboarding.schema import get_cached_welcome_questions

_LOG_SAMPLE_LIMIT = 3


async def preload_onboarding_schema(delay_sec: float = 1.5) -> None:
    """Warm the onboarding question cache shortly after startup.

    The task tolerates failures and only logs outcomes, never raising upstream.
    """

    try:
        await asyncio.sleep(max(0.0, float(delay_sec)))
        questions = await get_cached_welcome_questions(force=True)
        count = len(questions)
        preview = ",".join(question.qid for question in questions[:_LOG_SAMPLE_LIMIT])
        if count == 0:
            log.human(
                "warning", "onb preload: 0 rows for flow=welcome (check sheet)"
            )
        else:
            log.human(
                "info", "onb preload ok", count=count, sample=preview
            )
    except Exception as exc:  # pragma: no cover - defensive logging
        log.human("warning", "onb preload failed", error=str(exc))
