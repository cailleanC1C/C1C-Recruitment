"""Entrypoint scaffold for the unified bot.

Phase 1 will implement:
- shared/health.py (aiohttp: /ready, /healthz)
- shared/socket_heartbeat.py (last event tracking)
- shared/watchdog.py (grace-based restart)
- shared/coreops_cog.py + shared/help.py (minimal CoreOps)
"""
if __name__ == "__main__":
    print("Scaffold ready. Implement Phase 1 modules and wire them here.")
