from __future__ import annotations

import pytest

from modules.community.shard_tracker.mercy import (
    MERCY_PROFILES,
    calculate_mercy,
    format_percent,
)


def test_calculate_mercy_before_threshold():
    profile = MERCY_PROFILES["sacred"]
    state = calculate_mercy(profile, 5)

    assert state.pulls_since == 5
    assert state.current_chance == pytest.approx(profile.base_rate)
    assert state.pulls_until_threshold == profile.threshold - 5
    assert state.pulls_until_guarantee == profile.guarantee - 5


def test_calculate_mercy_after_threshold():
    profile = MERCY_PROFILES["ancient"]
    pulls = profile.threshold + 5
    state = calculate_mercy(profile, pulls)

    expected_rate = profile.base_rate + (pulls - profile.threshold + 1) * profile.increment
    assert state.current_chance == pytest.approx(expected_rate)
    assert state.pulls_until_threshold == 0
    assert state.pulls_until_guarantee == profile.guarantee - pulls


def test_format_percent_precision():
    assert format_percent(0.0123) == "1.23%"
    assert format_percent(0.25) == "25.0%"
