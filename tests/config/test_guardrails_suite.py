from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2] / "scripts" / "ci"))

import guardrails_suite


def _configure_roots(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setattr(guardrails_suite, "ROOT", tmp_path)
    monkeypatch.setattr(guardrails_suite, "AUDIT_ROOT", tmp_path / "AUDIT")
    monkeypatch.setattr(guardrails_suite, "DOCS_ROOT", tmp_path / "docs")


def test_c03_detects_parent_import(tmp_path, monkeypatch):
    _configure_roots(tmp_path, monkeypatch)
    module_dir = tmp_path / "modules"
    module_dir.mkdir()
    target = module_dir / "sample.py"
    target.write_text("from ..utils import helper\n", encoding="utf-8")

    category = guardrails_suite.CategoryResult("Code (C)")
    guardrails_suite.check_c03(category)

    assert category.status == "fail"
    assert category.violations[0].rule_id == "C-03"


def test_d02_requires_footer(tmp_path, monkeypatch):
    _configure_roots(tmp_path, monkeypatch)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    doc = docs_dir / "Guide.md"
    doc.write_text("# Guide\nContent only\n", encoding="utf-8")

    category = guardrails_suite.CategoryResult("Docs (D)")
    guardrails_suite.check_d02(category)

    assert category.status == "fail"
    assert category.violations[0].rule_id == "D-02"


def test_g09_enforces_tests_and_docs_blocks():
    body = """Summary

Details here.
"""
    category = guardrails_suite.CategoryResult("Governance (G)")
    guardrails_suite.check_g09(category, body)

    assert category.status == "fail"
    assert category.violations[0].rule_id == "G-09"


def test_g03_requires_meta_block():
    body = """Summary only

Tests: Added
Docs: Added
"""
    category = guardrails_suite.CategoryResult("Governance (G)")
    guardrails_suite.check_g03(category, body)

    assert category.status == "fail"
    assert category.violations[0].rule_id == "G-03"
