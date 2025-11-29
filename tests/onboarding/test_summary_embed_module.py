from types import SimpleNamespace

from types import SimpleNamespace

from modules.onboarding.ui import summary_embed


def test_summary_embed_routes_promo_to_new_builder():
    author = SimpleNamespace(display_name="Recruit", display_avatar=None)
    answers = {
        "pr_ign": "Returning Hero",
        "pr_siege": False,
        "pr_cvc": 2,
        "pr_cvc_points": 60_000,
    }

    embed = summary_embed.build_summary_embed(
        "promo.r", answers, author, schema_hash="hash123", visibility=None
    )

    assert "Returning Hero" in (embed.description or "")
    war_section = next(field for field in embed.fields if field.name.startswith("⚔️"))
    assert "Siege participation" in war_section.value
    assert "Minimum CvC points:** 60 K" in war_section.value
