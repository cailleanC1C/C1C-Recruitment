"""Log tag helpers for CoreOps lifecycle messaging."""

from __future__ import annotations

WATCHER_TAG = "[watcher]"
LIFECYCLE_TAG = "[lifecycle]"
# set False next release to drop old tag
DUAL_TAG_LIFECYCLE = True


def lifecycle_tag() -> str:
    """Return the lifecycle log tag, honoring the dual-tag rollout window."""

    return "[watcher|lifecycle]" if DUAL_TAG_LIFECYCLE else LIFECYCLE_TAG


__all__ = ("WATCHER_TAG", "LIFECYCLE_TAG", "DUAL_TAG_LIFECYCLE", "lifecycle_tag")
