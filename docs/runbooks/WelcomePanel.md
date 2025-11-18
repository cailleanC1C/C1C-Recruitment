# Welcome Panel Operations

## Persistent button
- The **Open questions** button is wired to the persistent component ID `welcome.panel.open`.
- The view registers on startup and runs with `timeout=None`, so the button never expires between restarts.

## Stale panel recovery
- If the panel message disappears or Discord returns `Unknown Message`, react with 🎫 on the welcome post.
- The watcher reposts a fresh panel automatically and emits sequential logs: `result=stale_panel` then `event=panel_posted`.

## Logging and permissions snapshot
- Button clicks log `panel_button_clicked` with formatted `channel`, `thread`, and `parent` names alongside the actor handle.
- Each click includes `app_permissions` plus the raw snapshot for auditing missing permissions.

Doc last updated: 2025-10-31 (v0.9.7)
