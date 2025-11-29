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

from shared import logfmt
from c1c_coreops import tags


def test_lifecycle_tag_uses_logfmt_prefix():
    assert tags.lifecycle_tag() == f"{logfmt.LOG_EMOJI['lifecycle']} **CoreOps** —"


def test_lifecycle_prefix_constant_matches_function():
    assert tags.LIFECYCLE_PREFIX == tags.lifecycle_tag()
