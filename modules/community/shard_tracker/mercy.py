"""Mercy math helpers for shard tracking embeds and commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class MercyProfile:
    """Immutable description of a shard mercy track."""

    key: str
    label: str
    base_rate: float
    threshold: int
    increment: float
    guarantee: int


@dataclass(frozen=True)
class MercyState:
    """Derived mercy math for a specific pull count."""

    profile: MercyProfile
    pulls_since: int
    current_chance: float
    pulls_until_threshold: int
    pulls_until_guarantee: int

    @property
    def percent(self) -> float:
        return max(0.0, min(self.current_chance, 1.0)) * 100.0


def _clamp_rate(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return value


def calculate_mercy(profile: MercyProfile, pulls_since: int) -> MercyState:
    """Return the current mercy state for ``profile`` at ``pulls_since`` pulls."""

    pulls = max(0, int(pulls_since))
    if pulls < profile.threshold:
        chance = profile.base_rate
    else:
        bonus_pulls = pulls - profile.threshold + 1
        chance = profile.base_rate + bonus_pulls * profile.increment
    chance = _clamp_rate(chance)
    pulls_until_threshold = max(0, profile.threshold - pulls)
    pulls_until_guarantee = max(0, profile.guarantee - pulls)
    return MercyState(
        profile=profile,
        pulls_since=pulls,
        current_chance=chance,
        pulls_until_threshold=pulls_until_threshold,
        pulls_until_guarantee=pulls_until_guarantee,
    )


def format_percent(value: float) -> str:
    """Return a human-friendly percentage string."""

    pct = _clamp_rate(value) * 100.0
    if pct >= 10:
        return f"{pct:.1f}%"
    return f"{pct:.2f}%"


MERCY_PROFILES: Dict[str, MercyProfile] = {
    "ancient": MercyProfile(
        key="ancient",
        label="Ancient",
        base_rate=0.005,
        threshold=200,
        increment=0.005,
        guarantee=220,
    ),
    "void": MercyProfile(
        key="void",
        label="Void",
        base_rate=0.005,
        threshold=200,
        increment=0.005,
        guarantee=220,
    ),
    "sacred": MercyProfile(
        key="sacred",
        label="Sacred",
        base_rate=0.06,
        threshold=12,
        increment=0.02,
        guarantee=20,
    ),
    # Primal shards always produce a legendary; treat the legendary track as a
    # one-pull guarantee with a 100% rate so the UI can still render a block.
    "primal": MercyProfile(
        key="primal",
        label="Primal",
        base_rate=1.0,
        threshold=1,
        increment=0.0,
        guarantee=1,
    ),
    # Mythic pity math for primal shards.
    "primal_mythic": MercyProfile(
        key="primal_mythic",
        label="Primal Mythic",
        base_rate=0.10,
        threshold=10,
        increment=0.02,
        guarantee=20,
    ),
}

