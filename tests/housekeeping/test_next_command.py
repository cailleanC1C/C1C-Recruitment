from datetime import datetime, timedelta, timezone

from cogs import app_admin


class _DummyJob:
    def __init__(self, name: str, component: str) -> None:
        self.name = name
        self.component = component
        self.interval = timedelta(minutes=5)
        self.next_run = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        self.tag = None


def _runtime_with_jobs(jobs):
    class _Scheduler:
        def __init__(self, jobs):
            self.jobs = jobs

    class _Runtime:
        def __init__(self, jobs):
            self.scheduler = _Scheduler(jobs)

    return _Runtime(jobs)


def test_build_scheduler_overview_groups_components():
    runtime = _runtime_with_jobs([
        _DummyJob("onboarding_idle_watcher", "recruitment"),
        _DummyJob("cache_refresh", "default"),
    ])

    message = app_admin._build_scheduler_overview(runtime, None)

    assert "recruitment" in message
    assert "onboarding_idle_watcher" in message
    assert "cache_refresh" in message


def test_build_scheduler_overview_filters_components():
    runtime = _runtime_with_jobs([
        _DummyJob("onboarding_idle_watcher", "recruitment"),
        _DummyJob("cache_refresh", "default"),
    ])

    message = app_admin._build_scheduler_overview(runtime, "recruitment")

    assert "onboarding_idle_watcher" in message
    assert "cache_refresh" not in message


def test_build_scheduler_overview_handles_empty_filter():
    runtime = _runtime_with_jobs([])

    message = app_admin._build_scheduler_overview(runtime, "unknown")

    assert "no jobs under unknown" in message
