#!/usr/bin/env python3
import os, re, sys, time, pathlib, json
from typing import List, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "guardrails" / "RepositoryGuardrails.md"
AUDIT_DIR = ROOT / f"AUDIT/{time.strftime('%Y%m%d')}_GUARDRAILS"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
REPORT = AUDIT_DIR / "report.md"

errors: List[str] = []
notes: List[str] = []


def _echo_violation(rule_id, message, file_path=None, line_no=None):
    """
    Standardized single-line output that our workflow parser can read.
    Example:
      VIOLATION: GR-001 No new labels without contract approval file: .github/labels.yml line: 14
    """
    parts = [f"VIOLATION: {rule_id}", message]
    if file_path:
        parts.append(f"file: {file_path}")
    if line_no:
        parts.append(f"line: {line_no}")
    print(" ".join(parts))

def glob(paths: List[str]) -> List[pathlib.Path]:
    out=[]
    for p in paths:
        out.extend(ROOT.glob(p))
    return [p for p in out if p.exists()]

def has_phase_title(md: pathlib.Path) -> bool:
    txt = md.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"^#\s+.*phase", txt, flags=re.IGNORECASE|re.MULTILINE)
    return bool(m)

def footer_ok(md: pathlib.Path) -> bool:
    lines = md.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
    if not lines: return False
    return bool(re.match(r"^Doc last updated: \d{4}-\d{2}-\d{2} \(v0\.9\.\w+\)$", lines[-1]))

def md_links(md: pathlib.Path) -> List[Tuple[str,str]]:
    txt = md.read_text(encoding="utf-8", errors="ignore")
    return re.findall(r"\[([^\]]+)\]\(([^)]+)\)", txt)

def file_exists(rel: str) -> bool:
    return (ROOT / rel).exists()

def grep(patterns: List[str], in_paths: List[str]) -> List[Tuple[str,int,str]]:
    outs=[]
    for g in in_paths:
        for p in ROOT.glob(g):
            if p.is_dir() or not p.suffix in {".py",".md"}: continue
            try:
                for i,l in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(),1):
                    for pat in patterns:
                        if re.search(pat, l):
                            outs.append((str(p.relative_to(ROOT)), i, l.strip()))
            except Exception:
                pass
    return outs

def section(title: str) -> str:
    return f"\n## {title}\n"

# 1) Structure checks
bad_imports = grep(
    [r"\brecruitment\.", r"\bonboarding\.", r"\bplacement\."],
    ["**/*.py"]
)
# Allow only under modules/
bad_imports = [t for t in bad_imports if not t[0].startswith("modules/")]

legacy_coreops = [
    (rel, ln, line)
    for rel, ln, line in grep([r"\bshared\.coreops_"], ["**/*.py"])
]

for rel, ln, line in bad_imports:
    _echo_violation("S-01", "legacy import outside modules/*", rel, ln)
    errors.append(f"S-01: legacy import outside modules/* → {rel}:{ln}: `{line}`")

for rel, ln, line in legacy_coreops:
    _echo_violation("S-05", "coreops must not live under shared/*", rel, ln)
    errors.append(f"S-05: coreops must not live under shared/* → {rel}:{ln}: `{line}`")

# Ensure packages exist
for pkg in ["modules/recruitment", "modules/placement", "modules/onboarding", "shared/sheets"]:
    if not file_exists(f"{pkg}/__init__.py"):
        _echo_violation("S-08", "missing __init__.py", f"{pkg}/__init__.py")
        errors.append(f"S-08: missing __init__.py in {pkg}")

# 2) Coding checks
decorators_outside_cogs = grep(
    [r"@(?:commands\.command|bot\.command|tree\.command|app_commands\.command)"],
    ["**/*.py"]
)
decorators_outside_cogs = [t for t in decorators_outside_cogs if not t[0].startswith("cogs/")]
for rel, ln, line in decorators_outside_cogs:
    _echo_violation("S-03", "command decorator outside cogs/*", rel, ln)
    errors.append(f"S-03: command decorator outside cogs/* → {rel}:{ln}: `{line}`")

# 3) Docs checks
docs = [p for p in ROOT.glob("docs/**/*.md") if p.is_file()]
for md in docs:
    if has_phase_title(md):
        rel_md = str(md.relative_to(ROOT))
        _echo_violation("D-01", "'Phase' in title", rel_md)
        errors.append(f"D-01: 'Phase' in title → {rel_md}")
    if not footer_ok(md):
        rel_md = str(md.relative_to(ROOT))
        _echo_violation("D-02", "missing or malformed footer", rel_md)
        errors.append(f"D-02: missing or malformed footer → {rel_md}")

# 4) ENV parity (SSoT)
config_md = ROOT / "docs" / "ops" / "Config.md"
env_example = ROOT / ".env.example"
if config_md.exists() and env_example.exists():
    md_txt = config_md.read_text(encoding="utf-8", errors="ignore")
    keys_in_md = set(re.findall(r"`([A-Z][A-Z0-9_]+)`", md_txt))
    env_txt = env_example.read_text(encoding="utf-8", errors="ignore")
    keys_in_env = set(re.findall(r"^([A-Z][A-Z0-9_]+)=", env_txt, flags=re.MULTILINE))
    missing_in_env = sorted(k for k in keys_in_md if k not in keys_in_env)
    extra_in_env = sorted(k for k in keys_in_env if k not in keys_in_md)
    if missing_in_env:
        _echo_violation("D-03", "keys in Config.md missing in .env.example", str(env_example.relative_to(ROOT)))
        errors.append(f"D-03: keys in Config.md missing in .env.example → {missing_in_env}")
    if extra_in_env:
        _echo_violation("D-03", "keys in .env.example not documented in Config.md", str(config_md.relative_to(ROOT)))
        errors.append(f"D-03: keys in .env.example not documented in Config.md → {extra_in_env}")
else:
    notes.append("ENV parity skipped: docs/ops/Config.md or .env.example missing")

# Write report
out = ["# Guardrails Compliance Report", "", f"- Findings: {len(errors)} error(s)"]
if notes:
    out.append(f"- Notes: {len(notes)}")
    for n in notes: out.append(f"  - {n}")
out.append(section("Errors"))
out.extend([f"- {e}" for e in errors] or ["- None"])

REPORT.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"Wrote {REPORT}")
sys.exit(1 if errors else 0)
