#!/usr/bin/env python3
"""Summarize welcome-flow diagnostics into a structured PR comment."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
PANELS_PATH = Path("modules") / "onboarding" / "ui" / "panels.py"
WELCOME_CONTROLLER_PATH = Path("modules") / "onboarding" / "controllers" / "welcome_controller.py"


@dataclass
class Hypothesis:
    priority: int
    title: str
    evidence: str


def load_events(log_path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not log_path.exists():
        return events
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping):
            events.append(dict(payload))
    return events


def _collect_registered_custom_ids(events: Iterable[dict[str, Any]]) -> set[str]:
    custom_ids: set[str] = set()
    for event in events:
        if event.get("event") != "persistent_view_registered":
            continue
        for custom_id in event.get("custom_ids", []) or []:
            if isinstance(custom_id, str):
                custom_ids.add(custom_id)
    return custom_ids


def _format_registration_summary(events: Iterable[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    duplicates = 0
    for event in events:
        if event.get("event") != "persistent_view_registered":
            continue
        view = event.get("view")
        custom_ids = ", ".join(sorted(event.get("custom_ids", []) or [])) or "-"
        line = (
            f"- `{view}` registered={event.get('registered')} timeout={event.get('timeout')} "
            f"disable_on_timeout={event.get('disable_on_timeout')} custom_ids=[{custom_ids}]"
        )
        if event.get("duplicate_registration"):
            duplicates += 1
            stacksite = event.get("stacksite")
            if stacksite:
                line += f" (duplicate @ {stacksite})"
            else:
                line += " (duplicate)"
        lines.append(line)
    if not lines:
        lines.append("- No persistent registrations captured.")
    return lines


def _format_panel_summary(events: Iterable[dict[str, Any]], registered_ids: set[str]) -> list[str]:
    count = 0
    mismatched = 0
    custom_ids: set[str] = set()
    for event in events:
        if event.get("event") != "panel_posted":
            continue
        count += 1
        custom_id = event.get("custom_id")
        if isinstance(custom_id, str):
            custom_ids.add(custom_id)
            if custom_id not in registered_ids:
                mismatched += 1
    summary: list[str] = [f"- Panel messages observed: {count}"]
    if custom_ids:
        formatted = ", ".join(sorted(custom_ids))
        summary.append(f"- Custom IDs attached: [{formatted}]")
    if mismatched:
        summary.append(f"- ⚠️ {mismatched} panel(s) used unregistered custom IDs")
    return summary


def _format_click_summary(events: Iterable[dict[str, Any]]) -> list[str]:
    clicks = 0
    response_done_before_modal = 0
    followup_errors = 0
    missing_thread_perms = 0
    for event in events:
        name = event.get("event")
        if name == "panel_button_clicked":
            clicks += 1
            permissions = event.get("app_permissions", {}) or {}
            if isinstance(permissions, Mapping):
                if not permissions.get("send_messages_in_threads", True):
                    missing_thread_perms += 1
        elif name == "modal_launch_pre" and event.get("response_is_done"):
            response_done_before_modal += 1
        elif name == "deny_notice_error":
            status = event.get("status")
            code = event.get("code")
            if status == 403 or status == 404 or code in (10008, "10008"):
                followup_errors += 1
    lines = [f"- Clicks captured: {clicks}"]
    lines.append(f"- response_is_done before modal: {response_done_before_modal}")
    lines.append(f"- 403/404/10008 errors: {followup_errors}")
    if missing_thread_perms:
        lines.append(
            f"- send_messages_in_threads missing on {missing_thread_perms} interaction(s)"
        )
    else:
        lines.append("- send_messages_in_threads missing on 0 interaction(s)")
    return lines


def _format_timeout_summary(events: Iterable[dict[str, Any]]) -> list[str]:
    timeouts = [event for event in events if event.get("event") == "panel_view_timeout"]
    if not timeouts:
        return ["- No timeouts observed."]
    lines = [f"- Timeouts observed: {len(timeouts)}"]
    disabled = sum(1 for event in timeouts if event.get("disabled_components"))
    lines.append(f"- Components disabled on timeout: {disabled}")
    attempted_edit = sum(1 for event in timeouts if event.get("edit_attempted"))
    attempted_post = sum(1 for event in timeouts if event.get("post_attempted"))
    lines.append(f"- Edit attempts on timeout: {attempted_edit}")
    lines.append(f"- Post attempts on timeout: {attempted_post}")
    return lines


def _build_hypotheses(events: Iterable[dict[str, Any]]) -> list[Hypothesis]:
    registered = [event for event in events if event.get("event") == "persistent_view_registered"]
    duplicate = any(event.get("duplicate_registration") for event in registered)
    mismatched_custom = False
    registered_ids = _collect_registered_custom_ids(events)
    for event in events:
        if event.get("event") == "panel_posted":
            custom_id = event.get("custom_id")
            if isinstance(custom_id, str) and registered_ids and custom_id not in registered_ids:
                mismatched_custom = True
                break

    ack_conflicts = sum(
        1 for event in events if event.get("event") == "modal_launch_pre" and event.get("response_is_done")
    )
    skip_events = sum(1 for event in events if event.get("event") == "modal_launch_skipped")
    perm_miss = sum(
        1
        for event in events
        if event.get("event") == "panel_button_clicked"
        and isinstance(event.get("app_permissions"), Mapping)
        and not event["app_permissions"].get("send_messages_in_threads", True)
    )
    unknown_message = sum(
        1
        for event in events
        if event.get("event") == "deny_notice_error" and event.get("code") in (10008, "10008")
    )

    hypotheses: list[Hypothesis] = []
    if duplicate:
        hypotheses.append(
            Hypothesis(
                10,
                "Persistent view may be registering multiple times",
                "Duplicate registration events detected for the welcome panel view.",
            )
        )
    if mismatched_custom:
        hypotheses.append(
            Hypothesis(
                9,
                "Panel message custom_id mismatch",
                "Panel posts emitted a custom_id that was not part of the registered view.",
            )
        )
    if ack_conflicts or skip_events:
        hypotheses.append(
            Hypothesis(
                8,
                "Interactions acknowledged before modal launch",
                f"{ack_conflicts} modal launch attempt(s) saw response_is_done before send_modal; {skip_events} were skipped in diagnostics.",
            )
        )
    if perm_miss:
        hypotheses.append(
            Hypothesis(
                7,
                "Thread message permission missing",
                f"send_messages_in_threads was False on {perm_miss} click(s).",
            )
        )
    if unknown_message:
        hypotheses.append(
            Hypothesis(
                6,
                "Stale panel message referenced",
                f"Discord returned code 10008 for {unknown_message} deny/notice attempt(s).",
            )
        )
    if not hypotheses:
        hypotheses.append(
            Hypothesis(1, "No dominant issues detected", "Diagnostics did not surface obvious anomalies.")
        )
    return sorted(hypotheses, key=lambda item: item.priority, reverse=True)


def _line_for(path: Path, needle: str) -> int | None:
    file_path = REPO_ROOT / path
    if not file_path.exists():
        return None
    for index, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return index
    return None


def _build_next_steps(events: Iterable[dict[str, Any]]) -> list[str]:
    steps: list[str] = []
    registered = any(event.get("event") == "persistent_view_registered" and event.get("duplicate_registration") for event in events)
    ack_conflicts = any(
        event.get("event") in {"modal_launch_pre", "modal_launch_skipped"}
        and event.get("response_is_done")
        for event in events
    )
    perm_conflicts = any(
        event.get("event") == "panel_button_clicked"
        and isinstance(event.get("app_permissions"), Mapping)
        and not event["app_permissions"].get("send_messages_in_threads", True)
        for event in events
    )
    unknown_message = any(
        event.get("event") == "deny_notice_error" and event.get("code") in (10008, "10008")
        for event in events
    )

    if registered:
        line = _line_for(PANELS_PATH, "def register_persistent_views")
        anchor = (
            f"{PANELS_PATH.as_posix()}:L{line}"
            if line
            else PANELS_PATH.as_posix()
        )
        steps.append(f"- Guard persistent registration duplication in `{anchor}`")
    if ack_conflicts:
        line = _line_for(WELCOME_CONTROLLER_PATH, "_handle_modal_launch")
        anchor = (
            f"{WELCOME_CONTROLLER_PATH.as_posix()}:L{line}"
            if line
            else WELCOME_CONTROLLER_PATH.as_posix()
        )
        steps.append(f"- Enforce single-response modal launch in `{anchor}`")
    if perm_conflicts:
        line = _line_for(PANELS_PATH, "async def launch")
        anchor = (
            f"{PANELS_PATH.as_posix()}:L{line}"
            if line
            else PANELS_PATH.as_posix()
        )
        steps.append(f"- Harden thread permission checks in `{anchor}`")
    if unknown_message:
        line = _line_for(WELCOME_CONTROLLER_PATH, "_safe_ephemeral")
        anchor = (
            f"{WELCOME_CONTROLLER_PATH.as_posix()}:L{line}"
            if line
            else WELCOME_CONTROLLER_PATH.as_posix()
        )
        steps.append(f"- Handle stale panel cleanup in `{anchor}`")
    if not steps:
        steps.append("- Review welcome flow state machine for additional edge cases (no hot spots detected).")
    return steps


def build_comment(events: list[dict[str, Any]]) -> str:
    registered_ids = _collect_registered_custom_ids(events)
    parts = ["## Welcome Flow Findings"]
    parts.append("\n### Persistent Registration")
    parts.extend(_format_registration_summary(events))

    parts.append("\n### Panel Message")
    parts.extend(_format_panel_summary(events, registered_ids))

    parts.append("\n### Clicks & Responses")
    parts.extend(_format_click_summary(events))

    parts.append("\n### Timeouts")
    parts.extend(_format_timeout_summary(events))

    parts.append("\n### Top Hypotheses")
    for idx, hypothesis in enumerate(_build_hypotheses(events), 1):
        parts.append(f"{idx}. **{hypothesis.title}** — {hypothesis.evidence}")

    parts.append("\n### Next Steps (Fix PR)")
    parts.extend(_build_next_steps(events))

    return "\n".join(parts).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize welcome-flow diagnostics")
    parser.add_argument("--log", default="AUDIT/welcome_flow_diag.jsonl", help="Path to diagnostics JSONL")
    parser.add_argument("--output", help="Optional file to write the comment body")
    args = parser.parse_args()

    events = load_events(Path(args.log))
    comment = build_comment(events)
    if args.output:
        Path(args.output).write_text(comment, encoding="utf-8")
    else:
        print(comment)


if __name__ == "__main__":
    main()
