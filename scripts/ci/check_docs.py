#!/usr/bin/env python3
"""Docs linter enforcing collaboration contract rules."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
README = DOCS / "README.md"
CONFIG_DOC = DOCS / "ops" / "Config.md"
ENV_TEMPLATE = DOCS / "ops" / ".env.example"
FOOTER_RE = re.compile(r"^Doc last updated: \d{4}-\d{2}-\d{2} \(v0\.9\.\d+\)$")
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
HEADER_RE = re.compile(r"^# +(.+)$")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:")


def iter_markdown_files() -> list[Path]:
    return sorted(DOCS.rglob("*.md"))


def check_titles_and_footers(path: Path, errors: list[str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    h1 = None
    for line in lines:
        match = HEADER_RE.match(line)
        if match:
            h1 = match.group(1)
            break
    if h1 and "phase" in h1.lower():
        errors.append(f"{path.relative_to(ROOT)}: H1 contains forbidden word 'Phase'.")
    for raw in reversed(lines):
        if raw.strip():
            last = raw.strip()
            break
    else:
        last = ""
    if not FOOTER_RE.match(last):
        errors.append(f"{path.relative_to(ROOT)}: footer missing or malformed.")


def normalize_link(path: Path, target: str) -> Path | None:
    target = target.strip()
    if not target or target.startswith(EXTERNAL_PREFIXES) or target.startswith("#"):
        return None
    anchor_split = target.split("#", 1)
    link_path = anchor_split[0]
    if not link_path:
        return None
    resolved = (path.parent / link_path).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        return resolved
    return resolved


def check_links(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    for match in LINK_RE.finditer(text):
        target = match.group(1)
        resolved = normalize_link(path, target)
        if resolved is None:
            continue
        if not resolved.exists():
            rel = resolved if resolved.is_absolute() else resolved.relative_to(ROOT)
            errors.append(f"{path.relative_to(ROOT)}: broken link to {rel}.")


def parse_config_keys() -> set[str]:
    text = CONFIG_DOC.read_text(encoding="utf-8")
    try:
        section = text.split("## Environment keys", 1)[1].split("## Sheet config tabs", 1)[0]
    except IndexError:
        return set()
    keys = set()
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        if set(part.strip() for part in line.strip("|").split("|")) == {"---"}:
            continue
        first_cell = line.strip("|").split("|", 1)[0].strip()
        match = re.search(r"`([A-Z0-9_]+)`", first_cell)
        if match:
            keys.add(match.group(1))
    return keys


def parse_env_example_keys() -> set[str]:
    keys = set()
    for line in ENV_TEMPLATE.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        if "=" in line:
            key = line.split("=", 1)[0].strip()
            if key:
                keys.add(key)
    return keys


def check_readme_index(errors: list[str]) -> None:
    text = README.read_text(encoding="utf-8")
    linked: set[str] = set()
    for match in LINK_RE.finditer(text):
        target = match.group(1)
        resolved = normalize_link(README, target)
        if resolved is None:
            continue
        try:
            rel = resolved.relative_to(DOCS).as_posix()
        except ValueError:
            continue
        linked.add(rel)
    all_docs = {path.relative_to(DOCS).as_posix() for path in iter_markdown_files()}
    all_docs.discard("README.md")
    missing = sorted(all_docs - linked)
    if missing:
        errors.append("docs/README.md: missing links for -> " + ", ".join(missing))


def check_env_parity(errors: list[str]) -> None:
    config_keys = parse_config_keys()
    env_keys = parse_env_example_keys()
    if config_keys != env_keys:
        missing = sorted(config_keys - env_keys)
        extra = sorted(env_keys - config_keys)
        if missing:
            errors.append(
                "ENV parity: .env.example is missing keys -> " + ", ".join(missing)
            )
        if extra:
            errors.append(
                "ENV parity: .env.example has extra keys -> " + ", ".join(extra)
            )


def build_summary(errors: list[str]) -> list[str]:
    summary: list[str] = ["# Docs Lint Summary", ""]
    if errors:
        summary.append(f"- ❌ **Status:** {len(errors)} issue(s) detected")
        summary.append("- 📌 **Details:**")
        for line in errors[:10]:
            summary.append(f"  - {line}")
        if len(errors) > 10:
            remaining = len(errors) - 10
            summary.append(f"  - … {remaining} more issue(s) (see workflow logs)")
    else:
        summary.append("- ✅ **Status:** Documentation contract satisfied")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--summary",
        type=Path,
        help="Optional path to write a markdown summary for PR comments.",
    )
    args = parser.parse_args(argv)

    errors: list[str] = []
    for path in iter_markdown_files():
        check_titles_and_footers(path, errors)
        check_links(path, errors)
    check_readme_index(errors)
    check_env_parity(errors)

    if args.summary:
        summary_lines = build_summary(errors)
        args.summary.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
