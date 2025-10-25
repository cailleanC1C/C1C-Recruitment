import asyncio

from c1c_coreops.commands import reload


def test_reboot_triggers_runtime_restart(monkeypatch):
    called = {}

    async def fake_recreate_http_app():
        called["app"] = True

    monkeypatch.setattr(
        "modules.common.runtime.recreate_http_app",
        fake_recreate_http_app,
        raising=False,
    )

    class DummyBot:
        async def reload_extensions(self):
            called["ext"] = True

        async def start_reconnect_cycle(self):
            called["reconn"] = True

    reload.bot = DummyBot()

    asyncio.run(reload._handle_reboot())

    assert called == {"app": True, "ext": True, "reconn": True}
