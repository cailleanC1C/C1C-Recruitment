"""Smoke tests for c1c_coreops package imports."""

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


def test_prefix_imports() -> None:
    _ensure_src_on_path()

    from c1c_coreops import prefix

    assert hasattr(prefix, "detect_admin_bang_command")


class _DummyAuthor:
    def __init__(self, *, admin: bool) -> None:
        self.is_admin = admin


class _DummyMessage:
    def __init__(self, content: str, author: _DummyAuthor) -> None:
        self.content = content
        self.author = author


def _is_admin(user: object) -> bool:
    return bool(getattr(user, "is_admin", False))


def test_detect_admin_bang_command_for_admin() -> None:
    _ensure_src_on_path()

    from c1c_coreops.prefix import detect_admin_bang_command

    author = _DummyAuthor(admin=True)
    message = _DummyMessage(" !ENV  ", author)
    result = detect_admin_bang_command(
        message,
        commands=("Env", "Reload"),
        is_admin=_is_admin,
    )

    assert result == "Env"


def test_detect_admin_bang_command_for_non_admin() -> None:
    _ensure_src_on_path()

    from c1c_coreops.prefix import detect_admin_bang_command

    author = _DummyAuthor(admin=False)
    message = _DummyMessage("!reload", author)
    result = detect_admin_bang_command(
        message,
        commands=("Env", "Reload"),
        is_admin=_is_admin,
    )

    assert result is None


def test_detect_admin_bang_command_for_unknown() -> None:
    _ensure_src_on_path()

    from c1c_coreops.prefix import detect_admin_bang_command

    author = _DummyAuthor(admin=True)
    message = _DummyMessage("!unknown", author)
    result = detect_admin_bang_command(
        message,
        commands=("Env", "Reload"),
        is_admin=_is_admin,
    )

    assert result is None
