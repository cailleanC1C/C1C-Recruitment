"""Daily cron summary helpers kept import-safe for C-03 guardrail."""

from __future__ import annotations

import datetime as dt
import logging
from statistics import mean
from typing import Iterable

from c1c_coreops.cronlog import read_metrics

log = logging.getLogger("c1c.cron")
TAG = "[cron]"


def _p95(samples: list[int]) -> int:
    if not samples:
        return 0
    ordered = sorted(samples)
    index = int(0.95 * (len(ordered) - 1))
    return ordered[index]


async def emit_daily_summary(job_names: Iterable[str]) -> None:
    """Emit one summary line per job for the last 24h window."""

    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(hours=24)
    for name in job_names:
        runs = [
            entry
            for entry in await read_metrics(name)
            if dt.datetime.fromisoformat(entry["ts"]) >= cutoff
        ]
        count = len(runs)
        ok_count = sum(1 for entry in runs if entry.get("ok"))
        ok_pct = round(100 * ok_count / count, 1) if count else 0.0
        durations = [int(entry.get("dur_ms") or 0) for entry in runs]
        avg_ms = int(mean(durations)) if durations else 0
        p95_ms = _p95(durations)
        last_at = runs[-1]["ts"] if runs else "-"
        log.info(
            f"{TAG} summary job={name} runs={count} ok={ok_pct}% "
            f"p95_ms={p95_ms} avg_ms={avg_ms} last_at={last_at}"
        )
