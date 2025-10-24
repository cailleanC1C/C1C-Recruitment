#!/usr/bin/env python3
"""CoreOps packaging audit script.

This script scans the repository and flags legacy CoreOps packaging issues.
"""
from __future__ import annotations

import ast
import datetime as _dt
import os
from pathlib import Path
import re
import sys
from typing import Dict, Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = REPO_ROOT / "AUDIT"
REPORT_PATH = AUDIT_DIR / "CoreOps-Packaging-Audit.md"

IGNORE_DIR_NAMES = {".git", ".venv", "venv", ".mypy_cache", "__pycache__"}
PACKAGE_ROOT = REPO_ROOT / "packages" / "c1c-coreops"
ALLOWED_PACKAGE_ROOT = PACKAGE_ROOT / "src" / "c1c_coreops"
PATH_EXCEPTIONS = {REPO_ROOT / "scripts" / "audit_coreops_packaging.py"}
TEXT_FILE_EXTENSIONS = {
    ".py",
    ".md",
    ".rst",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
}

DOC_EXTENSIONS = {".md", ".rst", ".json", ".yaml", ".yml", ".toml"}

DOC_DRIFT_PATTERN = re.compile(r"shared[./]coreops(?!_)", re.IGNORECASE)
COREOPS_PATH_PATTERN = re.compile(r"coreops(?:_|$)")
BUILD_EMBED_PATTERN = re.compile(r"^build_.*_embed$")


class Offense:
    __slots__ = ("rule", "path", "line", "snippet")

    def __init__(self, rule: str, path: Path, line: Optional[int], snippet: str) -> None:
        self.rule = rule
        self.path = path
        self.line = line
        self.snippet = snippet.strip()


def is_under_allowed_package(path: Path) -> bool:
    try:
        path.resolve().relative_to(ALLOWED_PACKAGE_ROOT.resolve())
        return True
    except ValueError:
        return False


def should_ignore_path(path: Path) -> bool:
    if path == REPORT_PATH:
        return True
    try:
        path.relative_to(AUDIT_DIR)
        return True
    except ValueError:
        return False


def iter_repository_files(root: Path) -> Iterable[Path]:
    for item in root.iterdir():
        if item.is_dir():
            if item.name in IGNORE_DIR_NAMES:
                continue
            if should_ignore_path(item):
                continue
            yield from iter_repository_files(item)
        elif item.is_file():
            if should_ignore_path(item):
                continue
            yield item


def read_text_lines(path: Path) -> Optional[List[str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    return text.splitlines()


def check_legacy_imports(path: Path, lines: List[str], offenses: List[Offense]) -> None:
    if path.suffix != ".py" or is_under_allowed_package(path):
        return

    try:
        tree = ast.parse("\n".join(lines), filename=str(path))
    except SyntaxError:
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("shared.coreops"):
                    line_no = getattr(node, "lineno", None)
                    snippet = lines[line_no - 1] if line_no and line_no <= len(lines) else "import shared.coreops"
                    offenses.append(Offense("LEGACY_IMPORT", path, line_no, snippet))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("shared.coreops"):
                line_no = getattr(node, "lineno", None)
                snippet = lines[line_no - 1] if line_no and line_no <= len(lines) else f"from {module} import ..."
                offenses.append(Offense("LEGACY_IMPORT", path, line_no, snippet))


def check_path_offenses(path: Path, offenses: List[Offense]) -> None:
    if is_under_allowed_package(path):
        return
    if path in PATH_EXCEPTIONS:
        return
    try:
        path.resolve().relative_to(PACKAGE_ROOT.resolve())
        return
    except ValueError:
        pass
    relative_parts = path.relative_to(REPO_ROOT).parts
    if any(COREOPS_PATH_PATTERN.search(part.lower() if isinstance(part, str) else "") for part in relative_parts):
        offenses.append(Offense("STRAY_PATH", path, None, "Path contains coreops outside package"))


def check_shim_offenses(path: Path, lines: List[str], offenses: List[Offense]) -> None:
    if path.suffix != ".py" or is_under_allowed_package(path):
        return
    if "shared" not in path.relative_to(REPO_ROOT).parts:
        return

    try:
        tree = ast.parse("\n".join(lines), filename=str(path))
    except SyntaxError:
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("c1c_coreops"):
                for alias in node.names:
                    if alias.name == "*":
                        line_no = getattr(node, "lineno", None)
                        snippet = lines[line_no - 1] if line_no and line_no <= len(lines) else f"from {module} import *"
                        offenses.append(Offense("COREOPS_BRIDGE", path, line_no, snippet))
                        break


def check_duplicate_symbols(path: Path, lines: List[str], offenses: List[Offense]) -> None:
    if path.suffix != ".py" or is_under_allowed_package(path):
        return

    try:
        tree = ast.parse("\n".join(lines), filename=str(path))
    except SyntaxError:
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "CoreOpsCog":
            line_no = getattr(node, "lineno", None)
            snippet = lines[line_no - 1] if line_no and line_no <= len(lines) else "class CoreOpsCog"
            offenses.append(Offense("DUPLICATE_SYMBOL", path, line_no, snippet))
        elif isinstance(node, ast.FunctionDef):
            name = node.name
            if name in {"resolve_ops_log_channel_id", "detect_admin_bang_command"} or BUILD_EMBED_PATTERN.match(name):
                line_no = getattr(node, "lineno", None)
                snippet = lines[line_no - 1] if line_no and line_no <= len(lines) else f"def {name}(...):"
                offenses.append(Offense("DUPLICATE_SYMBOL", path, line_no, snippet))


def check_doc_drift(path: Path, lines: List[str], offenses: List[Offense]) -> None:
    if is_under_allowed_package(path):
        return
    if path.suffix not in DOC_EXTENSIONS:
        return

    for idx, line in enumerate(lines, start=1):
        if DOC_DRIFT_PATTERN.search(line):
            offenses.append(Offense("DOC_DRIFT", path, idx, line))


def build_report(offenses: List[Offense], files_scanned: int) -> str:
    timestamp = _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    commit_sha = (
        os.environ.get("GITHUB_SHA")
        if "GITHUB_SHA" in os.environ
        else "unknown"
    )
    status = "PASS" if not offenses else "FAIL"
    header = [
        "# CoreOps Packaging Audit",
        "",
        f"Generated: {timestamp}",
        f"Commit: {commit_sha}",
        f"Total files scanned: {files_scanned}",
        f"Result: **{status}** ({len(offenses)} offenses)",
        "",
    ]

    offenses_by_rule: Dict[str, List[Offense]] = {}
    for offense in offenses:
        offenses_by_rule.setdefault(offense.rule, []).append(offense)

    rule_titles = {
        "LEGACY_IMPORT": "Legacy Imports",
        "STRAY_PATH": "Stray CoreOps Paths",
        "COREOPS_BRIDGE": "Shim/Re-export Bridges",
        "DUPLICATE_SYMBOL": "Duplicate CoreOps Symbols",
        "DOC_DRIFT": "Docs/Config Drift",
    }

    body: List[str] = []
    for rule, rule_offenses in sorted(offenses_by_rule.items(), key=lambda item: rule_titles.get(item[0], item[0])):
        body.append(f"## {rule_titles.get(rule, rule)}")
        body.append("")
        body.append("| Path | Line | Snippet |")
        body.append("| --- | --- | --- |")
        for offense in sorted(rule_offenses, key=lambda o: (str(o.path), o.line or 0)):
            rel_path = offense.path.relative_to(REPO_ROOT)
            line_str = str(offense.line) if offense.line is not None else "-"
            snippet = offense.snippet.replace("|", "\\|")
            body.append(f"| `{rel_path}` | {line_str} | `{snippet}` |")
        body.append("")

    checklist = [
        "## Fix-It Checklist",
        "",
        "- Rewrite imports to use `c1c_coreops.*` directly.",
        "- Move or delete stray CoreOps files outside `packages/c1c-coreops`.",
        "- Remove shim files in `shared/` that re-export from `c1c_coreops`.",
        "- Delete duplicate CoreOps symbol definitions outside the package.",
        "- Update docs/configs to reference `c1c_coreops` paths only.",
    ]

    return "\n".join(header + body + checklist) + "\n"


def main() -> int:
    files_scanned = 0
    offenses: List[Offense] = []

    for path in iter_repository_files(REPO_ROOT):
        if path.is_dir():
            continue
        files_scanned += 1
        suffix = path.suffix.lower()
        lines = None
        if suffix in TEXT_FILE_EXTENSIONS:
            lines = read_text_lines(path)
        if suffix == ".py" and lines is not None:
            check_legacy_imports(path, lines, offenses)
            check_shim_offenses(path, lines, offenses)
            check_duplicate_symbols(path, lines, offenses)
        if lines is not None:
            check_doc_drift(path, lines, offenses)
        check_path_offenses(path, offenses)

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    report_content = build_report(offenses, files_scanned)
    REPORT_PATH.write_text(report_content, encoding="utf-8")

    if offenses:
        return 1
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except KeyboardInterrupt:
        exit_code = 1
    sys.exit(exit_code)
