import asyncio

from modules.recruitment.views import recruiter_panel as panel


class DummyCog:
    def unregister_panel(self, message_id: int) -> None:  # pragma: no cover - stub
        return None


class DummyResponse:
    def is_done(self) -> bool:
        return True


class DummyFollowup:
    async def send(self, *args, **kwargs) -> None:  # pragma: no cover - stub
        return None


class DummyInteraction:
    def __init__(self) -> None:
        self.response = DummyResponse()
        self.followup = DummyFollowup()


def _sample_rows() -> list[list[str]]:
    header = ["header"] * (panel.IDX_AF_INACTIVES + 1)
    row = [""] * (panel.IDX_AF_INACTIVES + 1)
    row[panel.COL_B_CLAN] = "Clan"
    row[panel.COL_C_TAG] = "#TAG"
    row[panel.COL_E_SPOTS] = "5"
    row[panel.IDX_AF_INACTIVES] = "1"
    return [header, row]


def test_recruiter_search_uses_to_thread(monkeypatch):
    async def runner() -> None:
        monkeypatch.setattr(panel.RecruiterPanelView, "_build_components", lambda self: None)
        monkeypatch.setattr(panel.RecruiterPanelView, "_sync_visuals", lambda self: None)

        view = panel.RecruiterPanelView(DummyCog(), author_id=1)
        interaction = DummyInteraction()

        captured = {"called": False, "fn": None}

        async def fake_to_thread(fn, *args, **kwargs):
            captured["called"] = True
            captured["fn"] = fn
            return _sample_rows()

        def fake_fetch(force: bool = False):
            return _sample_rows()

        async def fake_rebuild(self, interaction, *, ack_ephemeral=None):
            self._busy = False
            return None

        monkeypatch.setattr(panel.asyncio, "to_thread", fake_to_thread)
        monkeypatch.setattr(panel.recruitment_sheets, "fetch_clans", fake_fetch)
        monkeypatch.setattr(
            panel.RecruiterPanelView, "_rebuild_and_edit", fake_rebuild, raising=False
        )

        await view._run_search(interaction)

        assert captured["called"] is True
        assert captured["fn"] is fake_fetch

    asyncio.run(runner())
