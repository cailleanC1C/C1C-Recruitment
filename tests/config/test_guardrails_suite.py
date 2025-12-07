from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2] / "scripts" / "ci"))

import guardrails_suite


def _configure_roots(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setattr(guardrails_suite, "ROOT", tmp_path)
    monkeypatch.setattr(guardrails_suite, "AUDIT_ROOT", tmp_path / "AUDIT")
    monkeypatch.setattr(guardrails_suite, "DOCS_ROOT", tmp_path / "docs")


def test_c03_detects_parent_import(tmp_path: Path, monkeypatch: object) -> None:
    _configure_roots(tmp_path, monkeypatch)
    module_dir = tmp_path / "modules"
    module_dir.mkdir()
    target = module_dir / "sample.py"
    target.write_text("from ..utils import helper\n", encoding="utf-8")

    category = guardrails_suite.CategoryResult("Code (C)")
    guardrails_suite.check_c03(category)

    assert category.status == "fail"
    assert category.violations[0].rule_id == "C-03"


def test_d02_requires_footer(tmp_path: Path, monkeypatch: object) -> None:
    _configure_roots(tmp_path, monkeypatch)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    doc = docs_dir / "Guide.md"
    doc.write_text("# Guide\nContent only\n", encoding="utf-8")

    category = guardrails_suite.CategoryResult("Docs (D)")
    guardrails_suite.check_d02(category)

    assert category.status == "fail"
    assert category.violations[0].rule_id == "D-02"


def test_g09_enforces_tests_and_docs_blocks() -> None:
    body = """Summary

Details here.
"""
    category = guardrails_suite.CategoryResult("Governance (G)")
    guardrails_suite.check_g09(category, body)

    assert category.status == "fail"
    assert category.violations[0].rule_id == "G-09"


def test_g03_requires_meta_block() -> None:
    body = """Summary only

Tests: Added
Docs: Added
"""
    category = guardrails_suite.CategoryResult("Governance (G)")
    guardrails_suite.check_g03(category, body)

    assert category.status == "fail"
    assert category.violations[0].rule_id == "G-03"


def test_f04_uses_feature_registry_and_accessor(tmp_path: Path, monkeypatch: object) -> None:
    _configure_roots(tmp_path, monkeypatch)

    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()
    (modules_dir / "feature_usage.py").write_text(
        "from modules.common import feature_flags\n\n"
        "if feature_flags.is_enabled('member_panel'):\n"
        "    pass\n",
        encoding="utf-8",
    )

    category = guardrails_suite.CategoryResult("Features (F)")
    monkeypatch.setattr(
        guardrails_suite,
        "_load_feature_toggle_names",
        lambda: {"member_panel", "recruiter_panel"},
    )

    guardrails_suite.check_feature_toggles(category)

    assert category.status == "warn"
    assert category.violations[0].rule_id == "F-04"
    assert category.violations[0].files == ["recruiter_panel"]


def test_summary_reports_guardrail_health(tmp_path: Path, monkeypatch: object) -> None:
    _configure_roots(tmp_path, monkeypatch)

    docs_ops = tmp_path / "docs" / "ops"
    docs_ops.mkdir(parents=True)
    (docs_ops / ".env.example").write_text(
        "DISCORD_TOKEN=placeholder\nRECRUITMENT_SHEET_ID=sheet\n",
        encoding="utf-8",
    )

    config_md = docs_ops / "Config.md"
    config_md.write_text(
        "# Config\n\n## Environment keys\n\n| `DISCORD_TOKEN` | desc |\n| `RECRUITMENT_SHEET_ID` | desc |\n",
        encoding="utf-8",
    )

    categories = {"Docs": guardrails_suite.CategoryResult("Docs (D)")}
    config_status, secret_status, parity_status = guardrails_suite._compute_guardrail_health()

    summary_path = tmp_path / "summary.md"
    guardrails_suite._append_summary_markdown(
        categories,
        summary_path,
        parity_status,
        config_status,
        secret_status,
    )

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "Config parity: docs and .env template aligned" in summary_text
    assert "Secret scan: no Discord token patterns detected" in summary_text
