#!/usr/bin/env python3
"""CI guardrail for config/docs parity and token leak detection."""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENV_EXAMPLE = ROOT / "docs" / "ops" / ".env.example"
CONFIG_MD = ROOT / "docs" / "ops" / "Config.md"


def env_keys_from_example(path: pathlib.Path) -> list[str]:
    keys: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key:
                keys.append(key)
    return keys


def env_keys_from_docs(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    marker = "## Environment keys"
    start = text.find(marker)
    if start == -1:
        return []
    section = text[start + len(marker) :]
    next_heading = section.find("\n## ")
    if next_heading != -1:
        section = section[:next_heading]
    table_keys = set(
        re.findall(r"^\|\s*`([A-Z][A-Z0-9_]+)`\s*\|", section, flags=re.MULTILINE)
    )
    inline_keys = {
        match
        for match in re.findall(r"`([A-Z][A-Z0-9_]+)`", section)
        if "_" in match
    }
    keys = table_keys.union(inline_keys)
    return sorted(keys)


def check_discord_token_leak(repo_root: pathlib.Path) -> list[str]:
    # Allow any base64-url character for the user-id segment; tokens can begin with digits.
    pattern = re.compile(r"[A-Za-z\d_-]{23,28}\.[A-Za-z\d_-]{6}\.[A-Za-z\d_-]{27}")
    offenders: list[str] = []
    for path in repo_root.rglob("*"):
        if path.is_dir():
            continue
        if any(part.lower() == "audit" for part in path.parts):
            continue
        if any(part == ".git" for part in path.parts):
            continue
        if path.suffix.lower() in {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".mp4",
            ".pdf",
            ".ico",
            ".svg",
            ".csv",
            ".tsv",
            ".parquet",
            ".feather",
        }:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if pattern.search(content):
            offenders.append(str(path))
    return offenders


def main() -> None:
    example_keys = env_keys_from_example(ENV_EXAMPLE)
    doc_keys = env_keys_from_docs(CONFIG_MD)

    example_set = set(example_keys)
    doc_set = set(doc_keys)

    missing_in_docs = sorted(example_set - doc_set)
    missing_in_example = sorted(doc_set - example_set)

    exit_code = 0

    if missing_in_docs:
        print(
            "ERROR: Keys present in .env.example but missing in Config.md:",
            ", ".join(missing_in_docs),
        )
        exit_code = 1

    if missing_in_example:
        print(
            "ERROR: Keys documented in Config.md but missing in .env.example:",
            ", ".join(missing_in_example),
        )
        exit_code = 1

    offenders = check_discord_token_leak(ROOT)
    if offenders:
        print("ERROR: Potential Discord token pattern detected in files:")
        for offender in offenders:
            print(" -", offender)
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
