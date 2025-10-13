"""Entrypoint scaffold for the unified bot.

Phase 1 will implement:
- shared/health.py (aiohttp: /ready, /healthz)
- shared/socket_heartbeat.py (last event tracking)
- shared/watchdog.py (grace-based restart)
- shared/coreops_cog.py + shared/help.py (minimal CoreOps)
"""
if __name__ == "__main__":
    print("Scaffold ready. Implement Phase 1 modules and wire them here.")
    
# --- Health server wiring START ---
import asyncio

from config.runtime import (
    get_port,
    get_env_name,
    get_bot_name,
    get_watchdog_stall_sec,
)
from shared import socket_heartbeat as hb
from shared import health as health_srv

# later, inside your async main() or on_ready():
async def boot_health_server():
    site = await health_srv.start_server(
        heartbeat_probe=hb.age_seconds,
        bot_name=get_bot_name(),
        env_name=get_env_name(),
        port=get_port(),  # Render provides $PORT
        stale_after_sec=get_watchdog_stall_sec(),
    )
    return site
# --- Health server wiring END ---
