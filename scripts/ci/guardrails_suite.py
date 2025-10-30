"""Aggregate guardrails workflow runner."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence, Tuple
from urllib import error, request
import re

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
DOC_SPEC = ROOT / "docs" / "guardrails" / "RepositoryGuardrails.md"
ALLOWED_LABELS = ROOT / ".github" / "labels" / "labels.json"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from utils.md_rules import parse_guardrail_rules  # type: ignore  # noqa: E402
import label_compliance  # type: ignore  # noqa: E402


@dataclass(slots=True)
class CheckResult:
    area: str
    rule: str
    passed: bool
    details: str = ""
    gating: bool = True

    def status_cell(self) -> str:
        return "✅ Pass" if self.passed else "❌ Fail"


def _iter_python_files() -> Iterable[Path]:
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if any(part == "AUDIT" for part in rel.parts):
            continue
        yield path


def _iter_markdown_files() -> Iterable[Path]:
    docs_dir = ROOT / "docs"
    for path in docs_dir.rglob("*.md"):
        if path.is_file() and "AUDIT" not in path.parts:
            yield path


def _scan_patterns(paths: Iterable[Path], patterns: Sequence[re.Pattern[str]], *, allow_prefixes: Sequence[str] = ()) -> List[str]:
    violations: List[str] = []
    for file_path in paths:
        rel = file_path.relative_to(ROOT).as_posix()
        if any(rel.startswith(prefix) for prefix in allow_prefixes):
            continue
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for idx, line in enumerate(lines, 1):
            for pattern in patterns:
                if pattern.search(line):
                    violations.append(f"{rel}:{idx}")
    return violations


def scan_s01() -> Tuple[bool, List[str]]:
    patterns = [
        re.compile(r"(?<!modules\.)recruitment\.(?=[A-Za-z_])"),
        re.compile(r"(?<!modules\.)onboarding\.(?=[A-Za-z_])"),
        re.compile(r"(?<!modules\.)placement\.(?=[A-Za-z_])"),
    ]
    paths = [path for path in _iter_python_files() if not str(path.relative_to(ROOT)).startswith("modules/")]
    violations = _scan_patterns(paths, patterns)
    return (len(violations) == 0, violations)


def scan_s02() -> Tuple[bool, List[str]]:
    patterns = [
        re.compile(r"@(?:commands\.|bot\.|tree\.|app_commands\.)command"),
        re.compile(r"discord\.ext\.commands"),
    ]
    paths = [path for path in _iter_python_files() if str(path.relative_to(ROOT)).startswith("shared/")]
    violations = _scan_patterns(paths, patterns)
    return (len(violations) == 0, violations)


def scan_s03() -> Tuple[bool, List[str]]:
    patterns = [
        re.compile(r"@(?:commands\.|bot\.|tree\.|app_commands\.)command"),
    ]
    allow = ("cogs/", "packages/c1c-coreops/", "tests/")
    violations = _scan_patterns(_iter_python_files(), patterns, allow_prefixes=allow)
    return (len(violations) == 0, violations)


def scan_s05() -> Tuple[bool, List[str]]:
    domains = {p.name for p in (ROOT / "modules").iterdir() if p.is_dir()}
    conflicts: List[str] = []
    for domain in domains:
        for base in (ROOT / "shared", ROOT / "packages"):
            candidate = base / domain
            if candidate.exists():
                conflicts.append(candidate.relative_to(ROOT).as_posix())
    return (len(conflicts) == 0, conflicts)


def scan_s08() -> Tuple[bool, List[str]]:
    bases = [ROOT / "modules", ROOT / "shared", ROOT / "packages", ROOT / "cogs"]
    missing: List[str] = []
    for base in bases:
        if not base.exists():
            continue
        for directory in base.rglob("*"):
            if not directory.is_dir():
                continue
            if any(part == "__pycache__" for part in directory.parts):
                continue
            try:
                children = list(directory.iterdir())
            except Exception:
                continue
            if not any(child.suffix == ".py" for child in children):
                continue
            if not (directory / "__init__.py").exists():
                missing.append(directory.relative_to(ROOT).as_posix())
    return (len(missing) == 0, missing)


def scan_d01() -> Tuple[bool, List[str]]:
    violations: List[str] = []
    header_re = re.compile(r"^# +(.+)$")
    for path in _iter_markdown_files():
        rel = path.relative_to(ROOT).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            match = header_re.match(line)
            if match:
                if "phase" in match.group(1).lower():
                    violations.append(rel)
                break
    return (len(violations) == 0, violations)


def scan_d02() -> Tuple[bool, List[str]]:
    footer_re = re.compile(r"^Doc last updated: \d{4}-\d{2}-\d{2} \(v0\.9\.\d+\)$")
    violations: List[str] = []
    for path in _iter_markdown_files():
        rel = path.relative_to(ROOT).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            if line.strip():
                if not footer_re.match(line.strip()):
                    violations.append(rel)
                break
    return (len(violations) == 0, violations)


def _env_keys_from_example(path: Path) -> List[str]:
    keys: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key:
                keys.append(key)
    return keys


def _env_keys_from_docs(path: Path) -> List[str]:
    text = path.read_text(encoding="utf-8")
    marker = "## Environment keys"
    start = text.find(marker)
    if start == -1:
        return []
    section = text[start + len(marker) :]
    next_heading = section.find("\n## ")
    if next_heading != -1:
        section = section[:next_heading]
    keys = set(re.findall(r"`([A-Z][A-Z0-9_]+)`", section))
    return sorted(keys)


def scan_d03() -> Tuple[bool, List[str]]:
    config_doc = ROOT / "docs" / "ops" / "Config.md"
    env_example = ROOT / "docs" / "ops" / ".env.example"
    if not config_doc.exists() or not env_example.exists():
        return (False, ["Config.md or .env.example missing"])
    doc_keys = set(_env_keys_from_docs(config_doc))
    env_keys = set(_env_keys_from_example(env_example))
    missing_in_env = sorted(doc_keys - env_keys)
    missing_in_docs = sorted(env_keys - doc_keys)
    details: List[str] = []
    if missing_in_env:
        details.append("Missing in .env.example: " + ", ".join(missing_in_env))
    if missing_in_docs:
        details.append("Undocumented keys: " + ", ".join(missing_in_docs))
    return (not details, details)


def scan_d04() -> Tuple[bool, List[str]]:
    readme = ROOT / "docs" / "README.md"
    if not readme.exists():
        return (False, ["docs/README.md missing"])
    text = readme.read_text(encoding="utf-8")
    link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    linked: set[str] = set()
    docs_root = ROOT / "docs"
    for match in link_re.finditer(text):
        target = match.group(1)
        if target.startswith(("http://", "https://", "mailto:", "tel:", "#")):
            continue
        resolved = (readme.parent / target).resolve()
        try:
            rel = resolved.relative_to(docs_root).as_posix()
        except ValueError:
            continue
        linked.add(rel)
    all_docs = {path.relative_to(docs_root).as_posix() for path in _iter_markdown_files()}
    all_docs.discard("README.md")
    missing = sorted(all_docs - linked)
    return (len(missing) == 0, ["Missing links: " + ", ".join(missing)] if missing else [])


def run_secret_scan() -> List[str]:
    offenders: List[str] = []
    pattern = re.compile(r"[A-Za-z\d_-]{23,28}\.[A-Za-z\d_-]{6}\.[A-Za-z\d_-]{27}")
    for path in ROOT.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(ROOT)
        if any(part == "AUDIT" for part in rel.parts):
            continue
        if any(part == ".git" for part in rel.parts):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".pdf", ".ico", ".svg", ".csv", ".tsv"}:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if pattern.search(content):
            offenders.append(rel.as_posix())
    return offenders


def scan_c01() -> Tuple[bool, List[str]]:
    patterns = [re.compile(r"\btime\.sleep\("), re.compile(r"requests\.")]
    paths = [
        path
        for path in _iter_python_files()
        if not str(path.relative_to(ROOT)).startswith("tests/")
    ]
    violations = _scan_patterns(paths, patterns)
    return (len(violations) == 0, violations)


def scan_c02() -> Tuple[bool, List[str]]:
    pattern = re.compile(r"\bprint\(")
    paths = [
        path
        for path in _iter_python_files()
        if not str(path.relative_to(ROOT)).startswith("tests/")
    ]
    violations = _scan_patterns(paths, [pattern], allow_prefixes=("scripts/",))
    return (len(violations) == 0, violations)


def scan_c03() -> Tuple[bool, List[str]]:
    pattern = re.compile(r"from \.+")
    paths = [
        path
        for path in _iter_python_files()
        if not str(path.relative_to(ROOT)).startswith("tests/")
    ]
    violations = _scan_patterns(paths, [pattern])
    return (len(violations) == 0, violations)


def scan_c09() -> Tuple[bool, List[str]]:
    patterns = [re.compile(r"shared\.utils\.coreops_"), re.compile(r"recruitment/"), re.compile(r"onboarding/")]
    violations = _scan_patterns(_iter_python_files(), patterns)
    return (len(violations) == 0, violations)


SCANNERS: Dict[str, Callable[[], Tuple[bool, List[str]]]] = {
    "S-01": scan_s01,
    "S-02": scan_s02,
    "S-03": scan_s03,
    "S-05": scan_s05,
    "S-08": scan_s08,
    "C-01": scan_c01,
    "C-02": scan_c02,
    "C-03": scan_c03,
    "C-09": scan_c09,
    "D-01": scan_d01,
    "D-02": scan_d02,
    "D-03": scan_d03,
    "D-04": scan_d04,
}


def evaluate_guardrail_rules() -> List[CheckResult]:
    rules = parse_guardrail_rules(DOC_SPEC)
    results: Dict[str, CheckResult] = {}
    for rule in rules:
        results[rule.identifier] = CheckResult(
            area="Guardrails Doc",
            rule=f"{rule.identifier}: {rule.title}",
            passed=False,
            details="scanner missing",
        )

    for identifier, scanner in SCANNERS.items():
        if identifier not in results:
            continue
        passed, details = scanner()
        results[identifier].passed = passed
        results[identifier].details = ", ".join(details) if details else ""

    ordered = [results[rule.identifier] for rule in rules]
    return ordered


def evaluate_docs_contract() -> CheckResult:
    passed = True
    messages: List[str] = []

    s01, details01 = scan_d01()
    if not s01:
        passed = False
        messages.extend(details01)

    s02, details02 = scan_d02()
    if not s02:
        passed = False
        messages.extend(details02)

    s04, details04 = scan_d04()
    if not s04:
        passed = False
        messages.extend(details04)

    return CheckResult(
        area="Docs",
        rule="Documentation contract",
        passed=passed,
        details="; ".join(messages),
    )


def evaluate_config_and_secrets() -> Tuple[CheckResult, CheckResult]:
    parity_passed, parity_details = scan_d03()
    config_result = CheckResult(
        area="Config",
        rule="Docs ↔ .env.template parity",
        passed=parity_passed,
        details="; ".join(parity_details),
    )

    offenders = run_secret_scan()
    secrets_result = CheckResult(
        area="Secrets",
        rule="Discord token patterns",
        passed=len(offenders) == 0,
        details=", ".join(offenders),
    )
    return config_result, secrets_result


def evaluate_labels(pr_number: int, repo: str, token: str | None) -> CheckResult:
    result = label_compliance.evaluate_labels(
        repo=repo,
        number=pr_number,
        allowed_path=ALLOWED_LABELS,
        token=token,
    )
    details: List[str] = []
    passed = True
    if result.error:
        return CheckResult(
            area="Labels",
            rule=".github/labels/labels.json",
            passed=False,
            details=result.error,
        )
    if result.unknown:
        passed = False
        details.append("Unknown: " + ", ".join(result.unknown))
    if result.missing:
        passed = False
        details.append("Missing: at least one label")
    return CheckResult(
        area="Labels",
        rule=".github/labels/labels.json",
        passed=passed,
        details="; ".join(details),
    )


def build_table(rows: List[CheckResult]) -> str:
    lines = ["| Area | Rule/Section | Status | Details |", "|---|---|---|---|"]
    for row in rows:
        details = row.details.replace("|", "\\|")
        lines.append(f"| {row.area} | {row.rule} | {row.status_cell()} | {details} |")
    return "\n".join(lines)


def upsert_comment(*, repo: str, pr_number: int, body: str, token: str | None) -> None:
    comments_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    marker = "<!-- repository-guardrails -->"

    req = request.Request(comments_url, headers=headers)
    try:
        with request.urlopen(req, timeout=20) as resp:
            existing = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(f"Failed to list PR comments: {exc.code}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Unable to reach GitHub API: {exc.reason}") from exc

    comment_id = None
    for comment in existing:
        if isinstance(comment, dict) and isinstance(comment.get("body"), str) and marker in comment["body"]:
            comment_id = comment.get("id")
            break

    payload = json.dumps({"body": body}).encode("utf-8")
    if comment_id:
        url = f"{comments_url}/{comment_id}"
        req = request.Request(url, data=payload, headers=headers, method="PATCH")
    else:
        req = request.Request(comments_url, data=payload, headers=headers, method="POST")

    try:
        with request.urlopen(req, timeout=20):
            pass
    except error.HTTPError as exc:
        raise RuntimeError(f"Failed to post guardrails comment: {exc.code}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Unable to reach GitHub API: {exc.reason}") from exc


def run_suite(pr_number: int, repo: str, token: str | None) -> int:
    guardrail_results = evaluate_guardrail_rules()
    docs_result = evaluate_docs_contract()
    config_result, secrets_result = evaluate_config_and_secrets()
    labels_result = evaluate_labels(pr_number, repo, token)

    rows = guardrail_results + [docs_result, config_result, secrets_result, labels_result]
    table = build_table(rows)

    comment_body = "\n".join([
        "## Repository Guardrails",
        "",
        table,
        "",
        "<!-- repository-guardrails -->",
    ])

    upsert_comment(repo=repo, pr_number=pr_number, body=comment_body, token=token)

    exit_code = 0 if all(row.passed for row in rows if row.gating) else 1
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run guardrails suite and post aggregated results.")
    parser.add_argument("--pr", type=int, required=True, help="Pull request number")
    args = parser.parse_args(argv)

    repo = os.getenv("GITHUB_REPOSITORY")
    if not repo:
        print("GITHUB_REPOSITORY is not set", file=sys.stderr)
        return 2

    token = os.getenv("GITHUB_TOKEN")

    return run_suite(args.pr, repo, token)


if __name__ == "__main__":
    sys.exit(main())
