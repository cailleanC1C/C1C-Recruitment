"""Smoke tests for c1c_coreops package imports."""

from pathlib import Path
import sys


def _ensure_src_on_path() -> None:
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    src = root / "packages" / "c1c-coreops" / "src"
    src_str = str(src)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)


def test_imports() -> None:
    _ensure_src_on_path()

    import c1c_coreops  # noqa: F401
    from c1c_coreops import rbac
    from c1c_coreops.cog import CoreOpsCog  # noqa: F401

    assert hasattr(rbac, "admin_only")


def test_render_imports() -> None:
    _ensure_src_on_path()

    from c1c_coreops import render

    assert hasattr(render, "build_env_embed")
    assert hasattr(render, "DigestEmbedData")
