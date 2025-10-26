from pathlib import Path
import sys


def _ensure_src_on_path() -> None:
    root = Path(__file__).resolve().parents[3]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    src = root / "packages" / "c1c-coreops" / "src"
    src_str = str(src)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)


_ensure_src_on_path()

from c1c_coreops import tags


def test_lifecycle_tag_dual_phase_enabled():
    assert tags.DUAL_TAG_LIFECYCLE is True
    assert tags.lifecycle_tag() == "[watcher|lifecycle]"


def test_lifecycle_tag_single_phase(monkeypatch):
    monkeypatch.setattr(tags, "DUAL_TAG_LIFECYCLE", False)
    try:
        assert tags.lifecycle_tag() == tags.LIFECYCLE_TAG
    finally:
        monkeypatch.setattr(tags, "DUAL_TAG_LIFECYCLE", True)
