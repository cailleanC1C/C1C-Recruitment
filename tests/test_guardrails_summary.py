import os


def test_guardrails_doc_exists_and_lists_all_rules():
    path = "docs/guardrails/README.md"
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as handle:
        txt = handle.read()
    assert "Documentation Discipline" in txt
    assert "Codex PR Formatting Rules" in txt
