#!/usr/bin/env python3
"""Run guardrails suite and render the PR summary comment."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Sequence

from scripts.ci.guardrails_suite import CheckResult, run_all_checks


def render_guardrails_comment(results: Sequence[CheckResult]) -> str:
    lines: List[str] = []
    lines.append("Repository Guardrails summary")
    lines.append("")
    lines.append("Guardrails Summary")
    lines.append("")

    if not results:
        lines.append("❌ Guardrails suite produced no results – check CI configuration.")
        return "\n".join(lines)

    has_failures = any(result.status == "fail" for result in results)
    lines.append("❌ Guardrail violations found" if has_failures else "✅ All guardrail checks passed")
    lines.append("")
    lines.append("Automated guardrail checks")
    lines.append("")

    for result in sorted(results, key=lambda r: r.code):
        if result.status == "pass":
            emoji = "✅"
            suffix = ""
        elif result.status == "fail":
            emoji = "❌"
            count = len(result.violations or [])
            plural = "s" if count != 1 else ""
            suffix = f" ({count} violation{plural})"
        else:
            emoji = "⚪"
            reason = (result.reason or "").strip()
            suffix = f" (skipped{': ' + reason if reason else ''})"

        lines.append(f"- {emoji} {result.code} — {result.description}{suffix}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("guardrails-comment.md"), help="Where to write rendered markdown")
    parser.add_argument("--status-file", type=Path, default=None, help="Path to write pass/fail status")
    parser.add_argument("--base-ref", type=str, default=None, help="Base ref for diff (e.g., origin/main)")
    parser.add_argument("--pr", type=int, default=0, help="Pull request number if available")
    args = parser.parse_args(argv)

    results, _violations = run_all_checks(base_ref=args.base_ref, pr_number=args.pr)
    markdown = render_guardrails_comment(results)

    exit_code = 1 if not results or any(result.status == "fail" for result in results) else 0
    args.output.write_text(markdown + "\n", encoding="utf-8")
    if args.status_file:
        args.status_file.write_text("fail" if exit_code else "pass", encoding="utf-8")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
