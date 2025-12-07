#!/usr/bin/env python3
"""Emit GitHub annotations for docs and guardrails checks."""
from __future__ import annotations

import argparse
import logging
import pathlib
import re
import sys
from typing import Iterable

from scripts.ci.utils.env import get_env_path

log = logging.getLogger(__name__)

DOCS_PATTERNS: list[re.Pattern[str]] = [
    # e.g. "docs/README.md: footer missing or malformed."
    re.compile(r"^(?P<file>[\w\-/\.]+):\s*(?P<msg>footer missing or malformed)\.?$", re.IGNORECASE),
    # e.g. "docs/README.md: missing links for -> Architecture.md, _meta/DocStyle.md"
    re.compile(r"^(?P<file>[\w\-/\.]+):\s*missing links for\s*->\s*(?P<msg>.+)$", re.IGNORECASE),
]

GR_PATTERNS: list[re.Pattern[str]] = [
    # Guardrails output lines look like:
    #   VIOLATION: S-01 legacy import outside modules/* file: modules/foo.py line: 12
    re.compile(
        r"^VIOLATION:\s*(?P<rule>[A-Z0-9\-_.]+)\s+(?P<msg>.+?)\s+file:\s*(?P<file>[\w\-/\.]+)"
        r"(?:\s+line:\s*(?P<line>\d+))?\s*$",
        re.IGNORECASE,
    ),
]


def emit_error(file_path: str, line: str | int | None, title: str, message: str) -> None:
    """Write a GitHub annotation to stdout."""
    try:
        line_no = int(line) if line is not None else 1
    except (TypeError, ValueError):
        line_no = 1
    log.error("::error file=%s,line=%s,title=%s::%s", file_path, line_no, title, message)


def append_summary(entries: Iterable[str]) -> None:
    """Append a short summary to the GitHub step summary if available."""
    summary_path = get_env_path("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("### Check results\n\n")
        entries = list(entries)
        if not entries:
            handle.write("All clear.\n")
            return
        for entry in entries:
            handle.write(f"- {entry}\n")


def parse_docs(text: str) -> list[str]:
    findings: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        for pattern in DOCS_PATTERNS:
            match = pattern.match(stripped)
            if not match:
                continue
            data = match.groupdict()
            emit_error(data["file"], 1, "Docs check", data["msg"])
            findings.append(f"{data['file']}: {data['msg']}")
            break
    return findings


def parse_guardrails(text: str) -> list[str]:
    findings: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        for pattern in GR_PATTERNS:
            match = pattern.match(stripped)
            if not match:
                continue
            data = match.groupdict()
            title = f"Guardrail {data['rule']}"
            message = data["msg"]
            emit_error(data["file"], data.get("line"), title, message)
            location = data["file"]
            if data.get("line"):
                location = f"{location}:{data['line']}"
            findings.append(f"{data['rule']}: {message} ({location})")
            break
    return findings


def parse(kind: str, text: str) -> list[str]:
    if kind == "docs":
        return parse_docs(text)
    if kind == "guardrails":
        return parse_guardrails(text)
    raise ValueError(f"unsupported kind: {kind}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("docs", "guardrails"), required=True)
    parser.add_argument("--input", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

    try:
        text = args.input.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        log.error("error: input file not found: %s", args.input)
        return 2

    findings = parse(args.kind, text)
    append_summary(findings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
