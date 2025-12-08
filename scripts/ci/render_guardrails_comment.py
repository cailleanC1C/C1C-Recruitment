#!/usr/bin/env python3
"""Render the guardrails PR comment from guardrails-results.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _load_guardrails_results(path: Path = Path("guardrails-results.json")) -> Dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _records_from_data(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = data.get("results")
    if isinstance(results, list):
        return results

    checks = data.get("checks")
    if isinstance(checks, dict):
        records: List[Dict[str, Any]] = []
        for code, info in checks.items():
            violations = info.get("violations") or []
            if isinstance(violations, int):
                violations = [None] * violations
            elif not isinstance(violations, list):
                violations = []

            records.append(
                {
                    "code": code,
                    "description": info.get("description") or code,
                    "status": info.get("status") or "fail",
                    "violations": violations,
                    "reason": info.get("reason"),
                }
            )
        return records

    return []


def render_guardrails_comment(data: Dict[str, Any]) -> str:
    checks = _records_from_data(data)

    lines: list[str] = []
    lines.append("Repository Guardrails summary")
    lines.append("")
    lines.append("Guardrails Summary")
    lines.append("")

    has_failures = any(check.get("status") == "fail" for check in checks)
    lines.append("❌ Guardrail violations found" if has_failures else "✅ All guardrail checks passed")
    lines.append("")

    lines.append("Automated guardrail checks")
    lines.append("")

    status_icons = {"pass": "✅", "fail": "❌", "skip": "⚪"}
    for check in sorted(checks, key=lambda c: c.get("code", "")):
        code = check.get("code", "UNK")
        desc = (check.get("description") or "").strip() or "No description"
        status = check.get("status") or "fail"
        icon = status_icons.get(status, "⚠️")

        suffix = ""
        if status == "fail":
            count = len(check.get("violations") or [])
            plural = "s" if count != 1 else ""
            suffix = f" ({count} violation{plural})"
        elif status == "skip":
            reason = (check.get("reason") or "not run").strip().rstrip(".")
            suffix = f" (skipped: {reason})"

        lines.append(f"- {icon} {code} — {desc}{suffix}")

    if not checks:
        lines.append("- ⚪ No guardrail checks found in guardrails-results.json")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("guardrails-results.json"),
        help="Path to guardrails-results.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("guardrails-comment.md"),
        help="Where to write rendered markdown",
    )
    args = parser.parse_args(argv)

    data = _load_guardrails_results(args.results)
    markdown = render_guardrails_comment(data)
    args.output.write_text(markdown + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
