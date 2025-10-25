"""Ensure CoreOps package can be imported without runtime env secrets."""

import importlib
import pathlib
import sys


def _ensure_src_on_path() -> None:
    root = pathlib.Path(__file__).resolve().parent.parent
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    src = root / "packages" / "c1c-coreops" / "src"
    src_str = str(src)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)


def test_import_coreops_without_env_vars(monkeypatch):
    for key in ("DISCORD_TOKEN", "GSPREAD_CREDENTIALS", "RECRUITMENT_SHEET_ID"):
        monkeypatch.delenv(key, raising=False)

    _ensure_src_on_path()
    module = importlib.import_module("c1c_coreops")

    assert hasattr(module, "__version__")
    assert module.__version__ == "0.0.0"
