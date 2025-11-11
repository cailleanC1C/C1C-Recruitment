from types import SimpleNamespace

from modules.onboarding import rules


def _question(order: str, qid: str, label: str, *, rule: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        order=order,
        order_raw=order,
        qid=qid,
        label=label,
        rules=rule,
    )


def test_evaluate_visibility_matches_label_targets() -> None:
    questions = [
        _question(
            "101",
            "stage",
            "Pick the option that matches your stage best.",
            rule="if early game skip Hydra Clash score",
        ),
        _question(
            "201",
            "hydra_score",
            "What’s your average Hydra Clash score?",
        ),
    ]

    answers = {"stage": {"value": "early_game", "label": "Early game"}}

    visibility = rules.evaluate_visibility(questions, answers)

    assert visibility["hydra_score"]["state"] == "skip"
