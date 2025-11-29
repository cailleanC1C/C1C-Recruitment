from types import SimpleNamespace

from modules.recruitment.summary_embed import build_promo_summary_embed


def _visibility_map(answers: dict[str, object]) -> dict[str, dict[str, str]]:
    return {gid: {"state": "show"} for gid in answers}


def test_promo_r_summary_formatting_and_visibility():
    answers = {
        "pr_ign": "Returning Hero",
        "pr_power": 1_250_000,
        "pr_level_detail": "Early Endgame",
        "pr_playstyle": "Competitive",
        "pr_prev_clan": "Old Guard",
        "pr_clan": "Hydra focus",
        "pr_CB": "Brutal",
        "pr_hydra_diff": "Nightmare",
        "pr_hydra_clash": 12_600,
        "pr_chimera_diff": "Normal",
        "pr_chimera_clash": 1_250_000,
        "pr_siege": "No",
        "pr_siege_detail": "Support squads",
        "pr_cvc": 5,
        "pr_cvc_points": 60_000,
        "pr_return_reason": "A" * 210,
        "pr_return_change": "Ready to rejoin",
        "pr_notes": "Eager to help",
    }
    visibility = _visibility_map(answers)
    author = SimpleNamespace(display_name="Lead", display_avatar=None, name="Lead")

    embed = build_promo_summary_embed("promo.r", answers, visibility, author=author)

    assert embed.title == "🔥 C1C • Returning player promo"
    assert "**Player:** Returning Hero" in (embed.description or "")
    assert "Power" in (embed.description or "")

    war_section = next(field for field in embed.fields if field.name.startswith("⚔️"))
    assert "Siege participation" in war_section.value
    assert "Siege setup" not in war_section.value
    assert "CvC priority:** High" in war_section.value
    assert "Minimum CvC points:** 60 K" in war_section.value

    context_section = next(field for field in embed.fields if "Return context" in field.name)
    assert "Reason for break" in context_section.value
    assert "…" in context_section.value


def test_promo_m_inline_pairs_and_siege_detail():
    answers = {
        "pm_ign": "Mover",
        "pm_power": 950,
        "pm_level_detail": "",
        "pm_playstyle": "Casual",
        "pm_current_clan": "Beta",
        "pm_clan_type": "Hydra",
        "pm_CB": "Nightmare",
        "pm_hydra_diff": "",
        "pm_hydra_clash": 320_000,
        "pm_chimera_diff": "Normal",
        "pm_chimera_clash": 0,
        "pm_siege": "Yes",
        "pm_siege_detail": "Defence anchor",
        "pm_cvc": "Medium",
        "pm_cvc_points": None,
        "pm_move_urgency": "Soon",
        "pm_move_date": "Next CvC",
        "pm_move_reason": "Rebalance clans",
        "pm_notes": "Ready to move",
    }
    visibility = _visibility_map(answers)
    embed = build_promo_summary_embed("promo.m", answers, visibility, author=None)

    performance_section = next(
        field for field in embed.fields if field.name.startswith("🧩 Performance")
    )
    assert "Avg Hydra Clash:** 320 K" in performance_section.value

    war_section = next(field for field in embed.fields if field.name.startswith("⚔️"))
    assert "Siege setup" in war_section.value
    assert "CvC priority" in war_section.value
    assert "Minimum CvC points" not in war_section.value
