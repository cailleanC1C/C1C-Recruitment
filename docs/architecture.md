# Architecture

```
Discord Gateway
  ↳ Event handlers (on_ready, on_message, on_connect, on_disconnect)
      ↳ Socket heartbeat tracker (READY / connect / disconnect timestamps, snapshots)
      ↳ Command layer (discord.py command tree with CoreOps cog)
          ↳ RBAC helper (parses ADMIN_ROLE_ID and STAFF_ROLE_IDS role memberships)

Watchdog loop
  ↳ Keepalive cadence probe (keepalive interval, stall detection)
  ↳ Disconnect grace timer and reconnect handling
  ↳ Latency measurements fed into CoreOps health output

Health server (aiohttp)
  ↳ /ready endpoint for Render routing
  ↳ /healthz endpoint for watchdog-aware checks
```

- CoreOps commands run inside the shared discord.py bot process alongside other cogs.
- Socket heartbeat state persists timestamps for READY events, the latest gateway
  connect, and the latest disconnect.
- The watchdog mirrors the legacy system: it schedules keepalive messages, measures
  stalls, and forces reconnects when the disconnect grace expires.
- Render restarts the container automatically whenever the bot exits.
