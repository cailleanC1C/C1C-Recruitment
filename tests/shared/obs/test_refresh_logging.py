from shared.logfmt import BucketResult
from shared.obs.events import format_refresh_message


def test_refresh_message_includes_onboarding_metadata() -> None:
    bucket = BucketResult(
        name="onboarding_questions",
        status="ok",
        duration_s=0.5,
        item_count=5,
        ttl_ok=True,
        retries=None,
        reason=None,
        metadata={"sheet": "abcdef", "tab": "OnboardingQuestions"},
    )

    message = format_refresh_message("startup", [bucket], total_s=0.5)

    assert "onboarding_questions ok" in message
    assert "sheet=abcdef" not in message
    assert "tab=OnboardingQuestions" not in message
    assert "0.5s" in message
