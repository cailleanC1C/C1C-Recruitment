import asyncio
import logging
import os
import sys
import time
import types
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("GSPREAD_CREDENTIALS", "{}")
os.environ.setdefault("RECRUITMENT_SHEET_ID", "sheet-id")

if "modules.common.runtime" not in sys.modules:
    runtime_stub = types.ModuleType("modules.common.runtime")

    def _monotonic_ms() -> int:
        return int(time.time() * 1000)

    runtime_stub.monotonic_ms = _monotonic_ms  # type: ignore[attr-defined]
    sys.modules["modules.common.runtime"] = runtime_stub

    modules_common = types.ModuleType("modules.common")
    modules_common.runtime = runtime_stub  # type: ignore[attr-defined]
    sys.modules.setdefault("modules.common", modules_common)

from shared import config as shared_config
import shared.sheets.cache_service as cache_service
from shared.sheets.cache_service import cache, register_onboarding_questions_bucket


@pytest.fixture(autouse=True)
def _register_bucket() -> None:
    register_onboarding_questions_bucket()
    bucket = cache.get_bucket("onboarding_questions")
    if bucket is not None:
        bucket.value = None
        bucket.last_refresh = None
        bucket.last_result = None
        bucket.last_error = None
        bucket.last_item_count = None


def test_startup_preload_success(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    async def runner() -> None:
        sample_rows = ({"flow": "welcome", "order": "1", "qid": "ign", "label": "IGN", "type": "short"},)
        monkeypatch.setattr(
            "shared.sheets.onboarding_questions.fetch_question_rows_async",
            AsyncMock(return_value=sample_rows),
        )
        monkeypatch.setitem(shared_config._CONFIG, "ONBOARDING_TAB", "Questions")

        caplog.set_level(logging.INFO, logger="shared.sheets.cache_service")

        await cache.refresh_now("onboarding_questions", actor="startup")

        bucket = cache.get_bucket("onboarding_questions")
        assert bucket is not None
        assert bucket.last_result in {"ok", "retry_ok"}
        assert bucket.last_item_count == 1

        messages = [record.message for record in caplog.records if "bucket=onboarding_questions" in record.message]
        assert messages, "expected refresh log entry"
        line = messages[-1]
        assert "trigger=manual" in line
        assert "actor=startup" in line
        assert "result=ok" in line
        assert "count=1" in line
        assert "error=-" in line

    asyncio.run(runner())


def test_startup_preload_missing_config(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    async def runner() -> None:
        async def _no_wait(_seconds: float) -> None:  # pragma: no cover - deterministic sleep
            return None

        monkeypatch.setattr(cache_service.asyncio, "sleep", _no_wait)
        monkeypatch.setattr(
            "shared.sheets.onboarding_questions.fetch_question_rows_async",
            AsyncMock(side_effect=KeyError("missing config key: ONBOARDING_TAB")),
        )

        caplog.set_level(logging.INFO, logger="shared.sheets.cache_service")

        await cache.refresh_now("onboarding_questions", actor="startup")

        bucket = cache.get_bucket("onboarding_questions")
        assert bucket is not None
        assert bucket.last_result == "fail"
        assert str(bucket.last_error or "").startswith("missing config key: ONBOARDING_TAB")

        messages = [record.message for record in caplog.records if "bucket=onboarding_questions" in record.message]
        assert messages, "expected refresh log entry"
        line = messages[-1]
        assert "trigger=manual" in line
        assert "actor=startup" in line
        assert "result=fail" in line
        assert "error=missing config key: ONBOARDING_TAB" in line

    asyncio.run(runner())
