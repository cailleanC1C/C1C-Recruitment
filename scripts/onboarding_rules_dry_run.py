#!/usr/bin/env python3
"""CLI helper to evaluate onboarding visibility rules locally."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from modules.onboarding import rules
from shared.sheets import onboarding_questions


def _load_answers(spec: str) -> Mapping[str, Any]:
    if spec.startswith("@"):
        path = Path(spec[1:])
        text = path.read_text(encoding="utf-8")
    else:
        text = spec
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover - user error
        raise SystemExit(f"Invalid answers payload: {exc}") from exc
    if not isinstance(data, Mapping):  # pragma: no cover - user error
        raise SystemExit("Answers payload must be a JSON object")
    return data


def _dump(data: Mapping[str, Any]) -> None:
    json.dump(data, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "answers",
        help="JSON object describing answers (prefix with @ to read from file)",
    )
    parser.add_argument(
        "--flow",
        default="welcome",
        choices=["welcome", "promo"],
        help="Question flow to evaluate (default: welcome)",
    )
    args = parser.parse_args(argv)

    answers = _load_answers(args.answers)
    questions = onboarding_questions.get_questions(args.flow)
    visibility = rules.evaluate_visibility(questions, answers)
    _dump(visibility)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
