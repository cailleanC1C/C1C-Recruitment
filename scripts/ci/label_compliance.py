"""PR label compliance helper."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence
from urllib import error, request

from scripts.ci.utils.env import get_env

log = logging.getLogger(__name__)


@dataclass(slots=True)
class LabelComplianceResult:
    unknown: List[str]
    missing: bool
    error: str | None = None


def _load_allowed_labels(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {str(item["name"]) for item in data if isinstance(item, dict) and "name" in item}
    raise ValueError("labels.json must be an array of objects with a 'name' field")


def _fetch_pr_labels(*, repo: str, number: int, token: str | None) -> List[str]:
    url = f"https://api.github.com/repos/{repo}/issues/{number}"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(url, headers=headers)
    try:
        with request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(f"GitHub API request failed with status {exc.code}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Unable to reach GitHub API: {exc.reason}") from exc

    labels = payload.get("labels", [])
    names: List[str] = []
    for label in labels:
        if isinstance(label, dict) and "name" in label:
            names.append(str(label["name"]))
    return names


def evaluate_labels(*, repo: str, number: int, allowed_path: Path, token: str | None) -> LabelComplianceResult:
    try:
        allowed = _load_allowed_labels(allowed_path)
    except Exception as exc:  # pragma: no cover - defensive
        return LabelComplianceResult(unknown=[], missing=False, error=str(exc))

    try:
        current = _fetch_pr_labels(repo=repo, number=number, token=token)
    except Exception as exc:  # pragma: no cover - defensive
        return LabelComplianceResult(unknown=[], missing=False, error=str(exc))

    unknown = sorted({label for label in current if label not in allowed})
    missing = len(current) == 0
    return LabelComplianceResult(unknown=unknown, missing=missing)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate PR labels against the repository allowlist.")
    parser.add_argument("--pr", type=int, required=True, help="Pull request number")
    parser.add_argument("--repo", required=True, help="GitHub repository (owner/name)")
    parser.add_argument("--allowed", type=Path, default=Path(".github/labels/labels.json"))
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    token = get_env("GITHUB_TOKEN")
    result = evaluate_labels(repo=args.repo, number=args.pr, allowed_path=args.allowed, token=token)

    if result.error:
        log.error(result.error)
        return 2

    messages: List[str] = []
    if result.missing:
        messages.append("No labels assigned to the pull request.")
    if result.unknown:
        messages.append("Unknown labels: " + ", ".join(result.unknown))

    if messages:
        log.error("; ".join(messages))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
