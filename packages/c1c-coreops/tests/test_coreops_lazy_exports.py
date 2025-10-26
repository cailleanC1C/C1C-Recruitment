import importlib
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


def test_c1c_coreops_lazy_exports_discoverable_without_imports():
    _ensure_src_on_path()

    pkg = importlib.import_module("c1c_coreops")
    names = dir(pkg)
    for module_name in ("cog", "config", "prefix", "rbac", "render", "tags"):
        assert module_name in names
    exported = getattr(pkg, "__exports__", {})
    for symbol in exported.keys():
        assert symbol in names
        assert symbol not in pkg.__dict__, "symbol should be lazily loaded, not bound at import time"
