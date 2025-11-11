"""Utility for managing persistent onboarding panel messages."""

from __future__ import annotations

import logging
from typing import Optional, Tuple

log = logging.getLogger("modules.onboarding.ui")


class PanelMessageManager:
    """Track and update the single active onboarding panel message per thread."""

    def __init__(self, state: dict | None) -> None:
        # ``state`` should act like a dict and is expected to hold a
        # ``_PANEL_MESSAGES`` mapping keyed by thread id. If it does not exist
        # yet we will create it on first use.
        self._state = state if state is not None else {}

    def _get_ids(self, thread_id: int) -> Tuple[int, Optional[int]]:
        panel_map = self._state.setdefault("_PANEL_MESSAGES", {})
        return thread_id, panel_map.get(thread_id)

    async def get_or_create(self, thread, *, embed=None, view=None, content=None):
        """Fetch the current panel message for ``thread`` or create it."""

        tid, mid = self._get_ids(thread.id)
        if mid:
            try:
                msg = await thread.fetch_message(mid)
                return await self._edit_existing(msg, embed=embed, view=view, content=content)
            except Exception:
                pass

        msg = await thread.send(content=content, embed=embed, view=view)
        self._state.setdefault("_PANEL_MESSAGES", {})[tid] = msg.id
        log.info("ui.panel.recreate • thread=%s • msg=%s • reason=missing", tid, msg.id)
        return msg

    async def _edit_existing(self, message, *, embed=None, view=None, content=None):
        await message.edit(content=content, embed=embed, view=view)
        return message

    async def edit(self, thread, *, embed=None, view=None, content=None) -> None:
        tid, mid = self._get_ids(thread.id)
        if not mid:
            await self.get_or_create(thread, embed=embed, view=view, content=content)
            return
        try:
            message = await thread.fetch_message(mid)
            await message.edit(content=content, embed=embed, view=view)
            log.info(
                "ui.panel.edit • thread=%s • msg=%s • view=%s",
                tid,
                mid,
                getattr(view, "__class__", type(view)).__name__ if view else None,
            )
        except Exception:
            message = await thread.send(content=content, embed=embed, view=view)
            self._state.setdefault("_PANEL_MESSAGES", {})[tid] = message.id
            log.info("ui.panel.recreate • thread=%s • msg=%s • reason=edit_failed", tid, message.id)

    async def delete(self, thread) -> None:
        tid, mid = self._get_ids(thread.id)
        if not mid:
            return
        try:
            message = await thread.fetch_message(mid)
            await message.delete()
        except Exception:
            pass
        self._state.get("_PANEL_MESSAGES", {}).pop(tid, None)

