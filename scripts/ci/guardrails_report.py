"""Render aggregated guardrails report comments."""
from __future__ import annotations

from typing import List, Sequence


_STATUS_METADATA = {
    "FAIL": ("❌", "Fail"),
    "PASS": ("✅", "Pass"),
    "NA": ("⚪", "N/A"),
}


def _summarize_checks(checks: Sequence["CheckResult"], *, limit: int = 10) -> str:
    names = [check.rule for check in checks]
    if not names:
        return "—"
    display = names[:limit]
    summary = ", ".join(display)
    extra = len(names) - limit
    if extra > 0:
        summary += f", +{extra} more"
    return summary


def _format_block_reason(check: "CheckResult") -> str:
    if check.details:
        if check.area == "Labels":
            return f"{check.rule}: {check.details[0]}"
        count = len(check.details)
        if all(":" in detail for detail in check.details):
            noun = "file" if count == 1 else "files"
            return f"{check.rule}: {count} {noun}"
        return f"{check.rule}: {check.details[0]}"
    return check.rule


def _format_fail_details(checks: Sequence["CheckResult"]) -> List[str]:
    lines: List[str] = []
    for check in checks:
        header = f"- **{check.rule}** ({check.area})"
        lines.append(header)
        for detail in check.details:
            lines.append(f"  - {detail}")
    return lines


def render_report(
    *,
    results: Sequence["CheckResult"],
    label_result: "CheckResult",
    job_failed: bool,
) -> str:
    table_lines = ["| Status | Checks |", "| --- | --- |"]
    grouped = {status: [] for status in _STATUS_METADATA}
    for check in results:
        grouped.setdefault(check.status, []).append(check)

    for status in ("FAIL", "PASS", "NA"):
        emoji, label = _STATUS_METADATA[status]
        checks = grouped.get(status, [])
        summary = _summarize_checks(checks)
        table_lines.append(f"| {emoji} {label} ({len(checks)}) | {summary} |")

    fail_checks = [check for check in results if check.status == "FAIL"]
    combined_failures: List["CheckResult"] = list(fail_checks)
    if label_result.status == "FAIL":
        combined_failures.append(label_result)

    body_lines: List[str] = ["## Repository Guardrails", "", *table_lines, ""]

    if job_failed and combined_failures:
        reasons = ", ".join(_format_block_reason(check) for check in combined_failures)
        body_lines.append(f"**Why blocked:** {reasons}")
        body_lines.append("")

    if fail_checks:
        body_lines.append("### Fail details")
        body_lines.extend(_format_fail_details(fail_checks))
        body_lines.append("")

    body_lines.append("### Label Compliance")
    if label_result.status == "PASS":
        body_lines.append("✓ Labels match the approved set.")
    else:
        detail = "; ".join(label_result.details) if label_result.details else "Label check failed."
        body_lines.append(f"✗ {detail}")
    body_lines.append("")
    body_lines.append("<!-- repository-guardrails -->")

    return "\n".join(body_lines)
