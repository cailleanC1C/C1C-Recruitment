"""Label compliance helper using Collaboration Contract."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List
from urllib import error, request
import re

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
CONTRACT_PATH = ROOT / "docs" / "contracts" / "CollaborationContract.md"


@dataclass(slots=True)
class LabelEvaluation:
    details: List[str]
    labels_ok: bool
    error: str | None = None


def _extract_section(text: str, heading: str) -> str:
    pattern = re.compile(rf"^## +{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        raise ValueError(f"Heading '{heading}' not found in contract")
    start = match.end()
    remainder = text[start:]
    next_heading = re.search(r"^## +", remainder, re.MULTILINE)
    if next_heading:
        remainder = remainder[: next_heading.start()]
    return remainder


def _parse_approved_labels(contract_path: Path = CONTRACT_PATH) -> set[str]:
    text = contract_path.read_text(encoding="utf-8")
    section = _extract_section(text, "6) Label Reference (Approved Set — full list)")
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    labels: set[str] = set()
    for line in lines:
        columns = [column.strip() for column in line.strip("|").split("|")]
        if not columns or columns[0].lower() == "name" or set(columns[0]) <= {"-", ""}:
            continue
        name = columns[0]
        if name:
            labels.add(name)
    if not labels:
        raise ValueError("No labels found in approved label table")
    return labels


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


def evaluate_labels(*, repo: str, number: int, token: str | None) -> LabelEvaluation:
    try:
        allowed = _parse_approved_labels()
    except Exception as exc:  # pragma: no cover - defensive
        return LabelEvaluation(details=[], labels_ok=False, error=str(exc))

    try:
        current = _fetch_pr_labels(repo=repo, number=number, token=token)
    except Exception as exc:  # pragma: no cover - defensive
        return LabelEvaluation(details=[], labels_ok=False, error=str(exc))

    details: List[str] = []
    labels_ok = True
    if not current:
        labels_ok = False
        details.append("No labels assigned to the pull request.")

    unknown = sorted({label for label in current if label not in allowed})
    if unknown:
        labels_ok = False
        details.append("Unknown labels: " + ", ".join(unknown))

    return LabelEvaluation(details=details, labels_ok=labels_ok)
