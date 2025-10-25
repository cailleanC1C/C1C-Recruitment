import asyncio

from modules.recruitment.reports import report_sheet


def test_reports_use_async_facade(monkeypatch):
    called = {}

    async def fake_read(sheet_id, rng):
        called["ok"] = (sheet_id, rng)
        return [["A", "B"]]

    monkeypatch.setattr("shared.sheets.async_facade.sheets_read", fake_read)

    out = asyncio.run(report_sheet.generate_report("sheet123", "Tab!A1:B2"))

    assert called.get("ok") == ("sheet123", "Tab!A1:B2")
    assert out == [["A", "B"]]
