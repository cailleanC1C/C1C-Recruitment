#!/usr/bin/env python3
"""Utility to format consistent markdown summaries for PR check comments."""

from __future__ import annotations

import argparse
import pathlib

STATUS_FORMAT = {
    "success": ("✅", "Completed successfully."),
    "failure": ("❌", "Failures detected."),
    "cancelled": ("⚠️", "Run was cancelled."),
    "skipped": ("⚠️", "Check was skipped."),
}


def build_lines(
    *,
    title: str,
    status: str,
    message: str | None,
    details_heading: str,
    details: list[str],
) -> list[str]:
    status_key = status.lower()
    emoji, default_message = STATUS_FORMAT.get(
        status_key,
        ("⚠️", f"Unhandled status '{status}'."),
    )
    summary_message = message if message else default_message

    lines = [f"# {title} Summary", "", f"- {emoji} **Status:** {summary_message}"]

    if details:
        lines.append(f"- 📌 **{details_heading}:**")
        for detail in details:
            lines.append(f"  - {detail}")

    return lines


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True, help="Human-friendly name of the check")
    parser.add_argument(
        "--status",
        required=True,
        help="Outcome of the check (success, failure, cancelled, skipped, ...)",
    )
    parser.add_argument(
        "--message",
        help="Custom message to accompany the status bullet.",
    )
    parser.add_argument(
        "--detail",
        action="append",
        default=[],
        dest="details",
        help="Additional bullet under the Details section (may be passed multiple times).",
    )
    parser.add_argument(
        "--details-heading",
        default="Details",
        help="Heading label for the details block (default: Details).",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=pathlib.Path,
        help="Where to write the markdown summary.",
    )

    args = parser.parse_args(argv)

    lines = build_lines(
        title=args.title,
        status=args.status,
        message=args.message,
        details_heading=args.details_heading,
        details=args.details,
    )
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
