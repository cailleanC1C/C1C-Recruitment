from pathlib import Path

import pytest

from scripts.ci.guardrails_suite import CheckResult
from scripts.ci.render_guardrails_comment import main, render_guardrails_comment


def test_render_guardrails_comment_includes_all_statuses():
    results = [
        CheckResult(
            code="C-02",
            description="Use logger instead of print()",
            status="pass",
            violations=[],
        ),
        CheckResult(
            code="C-03",
            description="Parent-relative imports are forbidden",
            status="fail",
            violations=[1, 2],
        ),
        CheckResult(
            code="D-04",
            description="README includes setup instructions",
            status="fail",
            violations=[1],
        ),
        CheckResult(
            code="G-03",
            description="PR body has [meta] block",
            status="skip",
            reason="PR body unavailable",
            violations=[],
        ),
    ]

    body = render_guardrails_comment(results)

    assert "Guardrails Summary" in body
    assert "✅ C-02 — Use logger instead of print()" in body
    assert "❌ C-03 — Parent-relative imports are forbidden (2 violations)" in body
    assert "❌ D-04 — README includes setup instructions (1 violation)" in body
    assert "⚪ G-03 — PR body has [meta] block (skipped: PR body unavailable)" in body


def test_render_guardrails_comment_handles_empty_results(tmp_path: Path) -> None:
    body = render_guardrails_comment([])

    assert "produced no results" in body
    assert "Config parity" not in body
    assert "Secret scan" not in body


def test_main_exits_nonzero_when_results_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "scripts.ci.render_guardrails_comment.run_all_checks", lambda base_ref=None, pr_number=0: ([], [])
    )

    output_path = tmp_path / "comment.md"
    status_path = tmp_path / "status.txt"

    exit_code = main(
        [
            "--output",
            str(output_path),
            "--status-file",
            str(status_path),
        ]
    )

    assert exit_code == 1
    assert "produced no results" in output_path.read_text(encoding="utf-8")
    assert status_path.read_text(encoding="utf-8") == "fail"
