#!/usr/bin/env python3
"""Audit the repository for COMMAND_PREFIX references."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

IGNORED_DIRS = {".git", "__pycache__", "venv", "env", ".venv", "AUDIT"}
TARGET = "COMMAND_PREFIX"


@dataclass(frozen=True)
class Hit:
    path: Path
    line_no: int
    line_text: str

    @property
    def is_python(self) -> bool:
        return self.path.suffix == ".py"


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _should_skip(path: Path) -> bool:
    return any(part in IGNORED_DIRS for part in path.parts)


def _iter_files(base: Path) -> Iterable[Path]:
    self_path = Path(__file__).resolve()
    for candidate in base.rglob("*"):
        if not candidate.is_file():
            continue
        if _should_skip(candidate.relative_to(base)):
            continue
        if candidate.resolve() == self_path:
            continue
        yield candidate


def _scan_file(path: Path) -> Iterable[Hit]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    hits: list[Hit] = []
    if TARGET not in text:
        return hits
    for line_no, line in enumerate(text.splitlines(), start=1):
        if TARGET in line:
            hits.append(Hit(path=path, line_no=line_no, line_text=line.strip()))
    return hits


def _write_report(root: Path, hits: list[Hit]) -> None:
    audit_dir = root / "AUDIT"
    audit_dir.mkdir(parents=True, exist_ok=True)
    report_path = audit_dir / "CommandPrefix-Audit.md"

    lines: list[str] = ["# COMMAND_PREFIX audit", ""]
    if not hits:
        lines.append("No occurrences of `COMMAND_PREFIX` were found.")
    else:
        lines.append(f"Found {len(hits)} occurrence(s) of `COMMAND_PREFIX`.")
        lines.append("")
        lines.append("| Path | Line | Context |")
        lines.append("| --- | --- | --- |")
        for hit in hits:
            context = hit.line_text.replace("|", "\\|")
            rel = hit.path.relative_to(root)
            lines.append(f"| `{rel}` | {hit.line_no} | `{context}` |")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    base = _root()
    hits: list[Hit] = []
    for path in _iter_files(base):
        hits.extend(_scan_file(path))

    _write_report(base, hits)

    if any(hit.is_python for hit in hits):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
