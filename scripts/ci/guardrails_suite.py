"""Repository guardrails enforcement suite.

This script implements automatable guardrails from ``docs/guardrails/RepositoryGuardrails.md``
and produces both a human-readable audit report and a machine-readable summary that
GitHub Actions can surface in PR comments.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
AUDIT_ROOT = ROOT / "AUDIT"
DOCS_ROOT = ROOT / "docs"

ALLOWED_EMBED_COLORS = {0xF200E5, 0x1B8009, 0x3498DB}
DOCUMENTED_TOGGLES = {
    "member_panel",
    "recruiter_panel",
    "recruitment_welcome",
    "recruitment_reports",
    "placement_target_select",
    "placement_reservations",
    "clan_profile",
    "welcome_dialog",
    "onboarding_rules_v2",
    "WELCOME_ENABLED",
    "ENABLE_WELCOME_HOOK",
    "ENABLE_PROMO_WATCHER",
    "housekeeping_keepalive",
    "housekeeping_cleanup",
    "mirralith_autoposter",
}


@dataclass
class Violation:
    rule_id: str
    severity: str  # "error" or "warning"
    message: str
    files: List[str] = field(default_factory=list)


@dataclass
class CategoryResult:
    identifier: str
    violations: List[Violation] = field(default_factory=list)

    @property
    def status(self) -> str:
        if any(v.severity == "error" for v in self.violations):
            return "fail"
        if self.violations:
            return "warn"
        return "pass"

    def add(self, violation: Violation) -> None:
        self.violations.append(violation)


def _iter_python_files() -> Iterable[Path]:
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if "AUDIT" in rel.parts:
            continue
        yield path


def _iter_markdown_files() -> Iterable[Path]:
    for path in DOCS_ROOT.rglob("*.md"):
        if "AUDIT" in path.parts:
            continue
        yield path


def _git_diff_names(base_ref: Optional[str]) -> List[str]:
    if base_ref:
        ref = base_ref
    else:
        ref = "HEAD^"
    cmd = ["git", "diff", "--name-only", f"{ref}..HEAD"]
    try:
        output = subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def _git_diff_status(base_ref: Optional[str]) -> Dict[str, str]:
    if base_ref:
        ref = base_ref
    else:
        ref = "HEAD^"
    cmd = ["git", "diff", "--name-status", f"{ref}..HEAD"]
    try:
        output = subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return {}
    mapping: Dict[str, str] = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        status, path = line.split("\t", 1)
        mapping[path] = status
    return mapping


def _load_pr_body(event_path: Optional[str]) -> str:
    if not event_path:
        return ""
    try:
        data = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except Exception:
        return ""
    return data.get("pull_request", {}).get("body", "") or ""


def _match_paths(paths: Iterable[Path], pattern: re.Pattern[str]) -> List[str]:
    hits: List[str] = []
    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for idx, line in enumerate(lines, 1):
            if pattern.search(line):
                hits.append(f"{rel}:{idx}")
    return hits


def check_s01_s05(category: CategoryResult) -> None:
    stray_domains = []
    candidates = {"recruitment", "onboarding", "placement", "community", "ops"}
    for candidate in candidates:
        path = ROOT / candidate
        if path.exists() and path.is_dir():
            stray_domains.append(path.relative_to(ROOT).as_posix())
    if stray_domains:
        category.add(Violation("S-01/S-05", "error", "Feature domains must live under modules/", stray_domains))


def check_s02(category: CategoryResult) -> None:
    pattern = re.compile(r"\bdiscord(\.ext\.commands)?")
    shared_files = [p for p in _iter_python_files() if p.relative_to(ROOT).as_posix().startswith("shared/")]
    hits = _match_paths(shared_files, pattern)
    if hits:
        category.add(Violation("S-02", "error", "Discord-specific imports not allowed in shared/", hits))


def check_s03(category: CategoryResult) -> None:
    pattern = re.compile(r"@(commands\.|bot\.|tree\.|app_commands\.)command")
    hits = _match_paths(_iter_python_files(), pattern)
    filtered = [h for h in hits if not h.startswith("cogs/") and not h.startswith("tests/")]
    if filtered:
        category.add(Violation("S-03", "error", "Command decorators must live under cogs/", filtered))


def check_s07_s09(category: CategoryResult, diff_status: Dict[str, str]) -> None:
    bad_audits: List[str] = []
    audit_re = re.compile(r"^AUDIT/\d{8}_.+")
    for path, status in diff_status.items():
        if not path.startswith("AUDIT/"):
            continue
        if status.upper() == "A" and not audit_re.match(path):
            bad_audits.append(path)
    if bad_audits:
        category.add(Violation("S-07", "error", "Audit artifacts must live under AUDIT/<YYYYMMDD>_*/", bad_audits))

    import_pattern = re.compile(r"from\s+AUDIT|import\s+AUDIT")
    runtime_files = [p for p in _iter_python_files() if not p.relative_to(ROOT).as_posix().startswith("tests/")]
    hits = _match_paths(runtime_files, import_pattern)
    if hits:
        category.add(Violation("S-09", "error", "Runtime code must not import AUDIT modules", hits))


def check_s08(category: CategoryResult) -> None:
    bases = [ROOT / "modules", ROOT / "shared", ROOT / "coreops"]
    missing: List[str] = []
    for base in bases:
        if not base.exists():
            continue
        for directory in base.rglob("*"):
            if not directory.is_dir():
                continue
            if any(part == "__pycache__" for part in directory.parts):
                continue
            if not any(child.suffix == ".py" for child in directory.iterdir() if child.is_file()):
                continue
            init_file = directory / "__init__.py"
            if not init_file.exists():
                missing.append(directory.relative_to(ROOT).as_posix())
    if missing:
        category.add(Violation("S-08", "error", "Packages must include __init__.py", missing))


def check_c02(category: CategoryResult) -> None:
    pattern = re.compile(r"\bprint\(")
    runtime_files = [p for p in _iter_python_files() if not p.relative_to(ROOT).as_posix().startswith(("scripts/", "tests/"))]
    hits = _match_paths(runtime_files, pattern)
    if hits:
        category.add(Violation("C-02", "error", "Use logger instead of print()", hits))


def check_c03(category: CategoryResult) -> None:
    pattern = re.compile(r"from \.+")
    runtime_files = [p for p in _iter_python_files() if not p.relative_to(ROOT).as_posix().startswith("tests/")]
    hits = _match_paths(runtime_files, pattern)
    if hits:
        category.add(Violation("C-03", "error", "Parent-relative imports are forbidden", hits))


def check_c09(category: CategoryResult) -> None:
    patterns = [re.compile(r"shared\.utils\.coreops_"), re.compile(r"recruitment/"), re.compile(r"onboarding/")]
    runtime_files = [p for p in _iter_python_files() if not p.relative_to(ROOT).as_posix().startswith("tests/")]
    hits: List[str] = []
    for path in runtime_files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for idx, line in enumerate(lines, 1):
            if any(pat.search(line) for pat in patterns):
                hits.append(f"{rel}:{idx}")
    if hits:
        category.add(Violation("C-09", "error", "Legacy paths must not be used", hits))


def check_c10(category: CategoryResult) -> None:
    pattern = re.compile(r"os\.getenv|os\.environ\[")
    allowed_prefixes = ("shared/config", "scripts/", "tests/")
    runtime_files = [p for p in _iter_python_files() if not p.relative_to(ROOT).as_posix().startswith(allowed_prefixes)]
    hits = _match_paths(runtime_files, pattern)
    if hits:
        category.add(Violation("C-10", "warning", "Use shared config accessor instead of ad-hoc env reads", hits))


def check_c11(category: CategoryResult) -> None:
    pattern = re.compile(r"get_port")
    hits = _match_paths(_iter_python_files(), pattern)
    hits = [h for h in hits if "check_forbidden_imports" not in h]
    if hits:
        category.add(Violation("C-11", "error", "Forbidden get_port import detected", hits))


def _extract_embed_color_violations() -> List[str]:
    offenders: List[str] = []
    for path in _iter_python_files():
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        class EmbedVisitor(ast.NodeVisitor):
            def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
                if isinstance(node.func, ast.Attribute) and node.func.attr == "Embed":
                    for kw in node.keywords:
                        if kw.arg in {"color", "colour"}:
                            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, int):
                                if kw.value.value not in ALLOWED_EMBED_COLORS:
                                    offenders.append(f"{rel}:{kw.value.lineno}")
                            elif isinstance(kw.value, ast.Name):
                                name = kw.value.id
                                if not re.match(r"[A-Z0-9_]*COLOR", name):
                                    offenders.append(f"{rel}:{kw.value.lineno}")
                self.generic_visit(node)
        EmbedVisitor().visit(tree)
    return offenders


def check_c17(category: CategoryResult) -> None:
    offenders = _extract_embed_color_violations()
    if offenders:
        category.add(Violation("C-17", "error", "Embed colours must use approved palette", offenders))


def _extract_toggle_usage() -> Dict[str, List[str]]:
    usage: Dict[str, List[str]] = {}
    pattern = re.compile(r"FeatureToggles\.[^(]*\(\s*[\"']([A-Za-z0-9_]+)[\"']")
    for path in _iter_python_files():
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for match in pattern.finditer(text):
            name = match.group(1)
            line_no = text[: match.start()].count("\n") + 1
            usage.setdefault(name, []).append(f"{rel}:{line_no}")
    return usage


def check_feature_toggles(category: CategoryResult) -> None:
    usage = _extract_toggle_usage()
    undocumented = [name for name in usage if name not in DOCUMENTED_TOGGLES]
    if undocumented:
        files: List[str] = []
        for toggle in undocumented:
            files.extend(usage.get(toggle, []))
        category.add(Violation("F-01", "error", "Toggle used but not documented", files))

    unused_documented = [name for name in DOCUMENTED_TOGGLES if name not in usage]
    if unused_documented:
        category.add(Violation("F-04", "warning", "Documented toggles not referenced in code", unused_documented))


def check_d01(category: CategoryResult) -> None:
    header_re = re.compile(r"^# +(.+)$")
    violations: List[str] = []
    for path in _iter_markdown_files():
        rel = path.relative_to(ROOT).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            match = header_re.match(line)
            if match:
                if "phase" in match.group(1).lower():
                    violations.append(rel)
                break
    if violations:
        category.add(Violation("D-01", "error", "Doc titles must not include 'Phase'", violations))


def check_d02(category: CategoryResult) -> None:
    footer_re = re.compile(r"^Doc last updated: \d{4}-\d{2}-\d{2} \(v0\.9\.8\.\d+\)$")
    violations: List[str] = []
    for path in _iter_markdown_files():
        rel = path.relative_to(ROOT).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            if line.strip():
                if not footer_re.match(line.strip()):
                    violations.append(rel)
                break
    if violations:
        category.add(Violation("D-02", "error", "Docs must end with standard footer", violations))


def check_d04_d08(category: CategoryResult) -> None:
    readme = DOCS_ROOT / "README.md"
    if not readme.exists():
        category.add(Violation("D-04", "error", "docs/README.md missing", []))
        return
    text = readme.read_text(encoding="utf-8")
    link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    linked: set[str] = set()
    for match in link_re.finditer(text):
        target = match.group(1)
        if target.startswith(("http://", "https://", "mailto:", "tel:", "#")):
            continue
        resolved = (readme.parent / target).resolve()
        try:
            rel = resolved.relative_to(DOCS_ROOT).as_posix()
        except ValueError:
            continue
        linked.add(rel)

    all_docs = {path.relative_to(DOCS_ROOT).as_posix() for path in _iter_markdown_files()}
    all_docs.discard("README.md")
    missing = sorted(all_docs - linked)
    if missing:
        category.add(Violation("D-04/D-08", "error", "Docs must be linked from docs/README.md", missing))


def check_d05(category: CategoryResult) -> None:
    adr_dir = DOCS_ROOT / "adr"
    bad: List[str] = []
    if adr_dir.exists():
        for path in adr_dir.glob("*.md"):
            if not re.match(r"ADR-\d{4}\.md", path.name):
                bad.append(path.relative_to(ROOT).as_posix())
    if bad:
        category.add(Violation("D-05", "error", "ADR files must follow ADR-XXXX.md naming", bad))


def check_d06(category: CategoryResult, diff_status: Dict[str, str]) -> None:
    new_audits = [path for path, status in diff_status.items() if path.startswith("AUDIT/") and status.upper() == "A"]
    if not new_audits:
        return
    changelog = ROOT / "CHANGELOG.md"
    if not changelog.exists():
        category.add(Violation("D-06", "error", "CHANGELOG.md missing for new audit entries", new_audits))
        return
    content = changelog.read_text(encoding="utf-8")
    missing: List[str] = []
    for audit_path in new_audits:
        if audit_path not in content:
            missing.append(audit_path)
    if missing:
        category.add(Violation("D-06", "error", "CHANGELOG must reference new AUDIT entries", missing))


def _parse_block(body: str, label: str) -> Optional[str]:
    pattern = re.compile(rf"{label}:\s*(.+)", re.IGNORECASE)
    match = pattern.search(body)
    if match:
        return match.group(1).strip()
    return None


def check_d09(category: CategoryResult, changed_files: List[str], pr_body: str) -> None:
    runtime_touched = any(f.startswith(("modules/", "shared/", "coreops/")) for f in changed_files)
    tests_touched = any(f.startswith("tests/") for f in changed_files)
    if not runtime_touched:
        return
    tests_block = _parse_block(pr_body, "Tests") or ""
    if tests_touched or tests_block:
        return
    category.add(Violation("D-09", "error", "Runtime changes require tests or Tests: declaration", changed_files))


def check_d10(category: CategoryResult, changed_files: List[str], pr_body: str) -> None:
    user_flow_change = any(f.startswith("cogs/") or f.startswith("modules/") for f in changed_files)
    docs_changed = any(f.startswith("docs/") for f in changed_files)
    if not user_flow_change:
        return
    docs_block = _parse_block(pr_body, "Docs") or ""
    if docs_changed or docs_block:
        return
    category.add(Violation("D-10", "error", "User-facing changes require docs or Docs: declaration", changed_files))


def check_g03(category: CategoryResult, pr_body: str) -> None:
    meta_block = re.search(r"\[meta\](.*?)\[/meta\]", pr_body, re.DOTALL | re.IGNORECASE)
    if not meta_block:
        category.add(Violation("G-03", "error", "PR body missing [meta] block with labels and milestone", []))
        return
    block = meta_block.group(1)
    if "labels:" not in block or "milestone:" not in block:
        category.add(Violation("G-03", "error", "[meta] block must include labels and milestone", []))


def check_g06(category: CategoryResult, diff_status: Dict[str, str]) -> None:
    added_docs = [path for path, status in diff_status.items() if status.upper() == "A" and path.startswith("docs/")]
    bad: List[str] = []
    for doc in added_docs:
        name = Path(doc).name
        if " " in name or "Phase" in name:
            bad.append(doc)
        elif not re.match(r"[a-z0-9_]+\.md", name):
            bad.append(doc)
    if bad:
        category.add(Violation("G-06", "error", "New docs must be lower_snake_case and avoid Phase", bad))


def check_g09(category: CategoryResult, pr_body: str) -> None:
    tests_block = _parse_block(pr_body, "Tests")
    docs_block = _parse_block(pr_body, "Docs")
    if not tests_block or not docs_block:
        category.add(Violation("G-09", "error", "PR body must declare Tests: and Docs: sections", []))


def _ensure_audit_report_path() -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    audit_dir = AUDIT_ROOT / f"{timestamp}_GUARDRAILS"
    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir / "report.md"


def _write_markdown_report(categories: Dict[str, CategoryResult], report_path: Path, parity_status: Optional[str]) -> None:
    lines: List[str] = ["# Repository Guardrails Report", ""]
    if parity_status:
        lines.append(f"ENV parity status: {parity_status}")
        lines.append("")
    for category in categories.values():
        icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}[category.status]
        lines.append(f"## {category.identifier} {icon}")
        if not category.violations:
            lines.append("No issues detected.")
        else:
            for violation in category.violations:
                lines.append(f"- **{violation.rule_id}** ({violation.severity}): {violation.message}")
                for file in violation.files:
                    lines.append(f"  - {file}")
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def _write_summary_json(categories: Dict[str, CategoryResult], path: Path, parity_status: Optional[str]) -> None:
    payload = {
        "overall_status": "fail" if any(cat.status == "fail" for cat in categories.values()) else "warn" if any(cat.status == "warn" for cat in categories.values()) else "pass",
        "parity_status": parity_status,
        "categories": [
            {
                "id": cat.identifier,
                "status": cat.status,
                "violations": [
                    {
                        "rule": v.rule_id,
                        "severity": v.severity,
                        "message": v.message,
                        "files": v.files,
                    }
                    for v in cat.violations
                ],
            }
            for cat in categories.values()
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _append_summary_markdown(categories: Dict[str, CategoryResult], path: Path, parity_status: Optional[str]) -> None:
    lines: List[str] = ["Repository Guardrails summary", ""]
    for cat in categories.values():
        icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}[cat.status]
        count = len(cat.violations)
        noun = "issues" if count != 1 else "issue"
        lines.append(f"{cat.identifier}: {icon} {count} {noun}")
    lines.append("")
    if parity_status:
        lines.append(f"D-03 ENV parity: {parity_status}")
        lines.append("")
    if any(cat.violations for cat in categories.values()):
        lines.append("Details:")
        for cat in categories.values():
            for violation in cat.violations:
                detail_files = ", ".join(violation.files) if violation.files else ""
                lines.append(f"- {violation.rule_id}: {violation.message}{' - ' + detail_files if detail_files else ''}")
    else:
        lines.append("No guardrail issues detected.")
    lines.append("")
    existing = ""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    path.write_text((existing + "\n" + "\n".join(lines)).strip() + "\n", encoding="utf-8")


def run_checks(
    base_ref: Optional[str], pr_body: str, parity_status: Optional[str], pr_number: int
) -> Dict[str, CategoryResult]:
    categories = {
        "Structure (S)": CategoryResult("Structure (S)"),
        "Code (C)": CategoryResult("Code (C)"),
        "Features (F)": CategoryResult("Features (F)"),
        "Docs (D)": CategoryResult("Docs (D)"),
        "Governance (G)": CategoryResult("Governance (G)"),
    }

    diff_status = _git_diff_status(base_ref)
    changed_files = _git_diff_names(base_ref)

    check_s01_s05(categories["Structure (S)"])
    check_s02(categories["Structure (S)"])
    check_s03(categories["Structure (S)"])
    check_s07_s09(categories["Structure (S)"], diff_status)
    check_s08(categories["Structure (S)"])

    check_c02(categories["Code (C)"])
    check_c03(categories["Code (C)"])
    check_c09(categories["Code (C)"])
    check_c10(categories["Code (C)"])
    check_c11(categories["Code (C)"])
    check_c17(categories["Code (C)"])

    check_feature_toggles(categories["Features (F)"])

    check_d01(categories["Docs (D)"])
    check_d02(categories["Docs (D)"])
    check_d04_d08(categories["Docs (D)"])
    check_d05(categories["Docs (D)"])
    check_d06(categories["Docs (D)"], diff_status)
    if pr_number > 0:
        check_d09(categories["Docs (D)"], changed_files, pr_body)
        check_d10(categories["Docs (D)"], changed_files, pr_body)

    if pr_number > 0:
        check_g03(categories["Governance (G)"], pr_body)
        check_g09(categories["Governance (G)"], pr_body)
    check_g06(categories["Governance (G)"], diff_status)

    if parity_status and parity_status.lower() == "failure":
        categories["Docs (D)"].add(Violation("D-03", "error", "ENV parity check failed", []))
    return categories


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run repository guardrails suite")
    parser.add_argument(
        "--pr", type=int, required=False, default=0, help="Pull request number if available"
    )
    parser.add_argument("--status-file", type=Path, default=None, help="Path to write overall status")
    parser.add_argument("--summary", type=Path, default=None, help="Path to append human-readable summary")
    parser.add_argument("--json", type=Path, default=Path("guardrails-results.json"), help="Where to write JSON summary")
    parser.add_argument("--base-ref", type=str, default=None, help="Base ref for diff (e.g., origin/main)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    pr_body = _load_pr_body(os.getenv("GITHUB_EVENT_PATH"))
    parity_status = os.getenv("ENV_PARITY_STATUS")
    categories = run_checks(args.base_ref, pr_body, parity_status, args.pr)

    report_path = _ensure_audit_report_path()
    _write_markdown_report(categories, report_path, parity_status)
    _write_summary_json(categories, args.json, parity_status)
    if args.summary:
        _append_summary_markdown(categories, args.summary, parity_status)

    overall_status = "fail" if any(cat.status == "fail" for cat in categories.values()) else "pass"
    if args.status_file:
        args.status_file.write_text(overall_status, encoding="utf-8")
    return 0 if overall_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
