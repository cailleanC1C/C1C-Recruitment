# Patch Plan — Port legacy keepalive/watchdog into unified bot

## Objectives
- Mirror the Matchmaker/WelcomeCrew watchdog heuristics so the unified bot exits when the gateway is stale or disconnected too long.
- Centralise gateway state (connected/ready/disconnect timestamps) for reuse by the watchdog and health probes.
- Tune keepalive cadence + stall thresholds per environment (prod vs non-prod) with env overrides.

## File-by-file changes

### `app.py`
**Before** (`on_ready`):
```py
hb.touch()
asyncio.create_task(watchdog.run(hb.age_seconds, stall_after_sec=stall, check_every=30))
log.info(f"Watchdog started (stall_after={stall}s)")
```

**After**:
```py
hb.note_ready()
keepalive = get_keepalive_interval_sec()
asyncio.create_task(
    watchdog.run(
        hb.age_seconds,
        stall_after_sec=stall,
        check_every=keepalive,
        state_probe=hb.snapshot,
        disconnect_grace_sec=disconnect_grace,
        latency_probe=lambda: getattr(bot, "latency", None),
    )
)
log.info(
    "Watchdog started (stall_after=%ss, interval=%ss, disconnect_grace=%ss)",
    stall,
    keepalive,
    disconnect_grace,
)
```
Key updates:
- Replace raw `touch()` with semantic `note_ready()`/`note_connected()`/`note_disconnected()` hooks.
- Drive watchdog with keepalive cadence + connection snapshot + latency probe.
- Log full watchdog configuration for operator visibility.

### `shared/socket_heartbeat.py`
**Before**:
```py
class _Heartbeat:
    def __init__(self) -> None:
        self._last_monotonic: float = time.monotonic()

    def touch_now(self) -> None:
        self._last_monotonic = time.monotonic()
```

**After**:
```py
@dataclass(frozen=True)
class GatewaySnapshot:
    connected: bool
    last_event_age: float
    last_ready_age: Optional[float]
    disconnect_age: Optional[float]
    ...

class _Heartbeat:
    def __init__(self) -> None:
        now = time.monotonic()
        self._last_event_ts: float = now
        self._last_ready_ts: Optional[float] = None
        self._last_disconnect_ts: Optional[float] = None
        self._connected: bool = False

    def note_connected(self) -> None:
        now = time.monotonic()
        self._connected = True
        self._last_event_ts = now
```
Key updates:
- Track READY/CONNECT/DISCONNECT timestamps and emit immutable `GatewaySnapshot` for watchdog.
- Expose helpers `note_ready`, `note_connected`, `note_disconnected`, `snapshot` in addition to `touch()`.

### `shared/watchdog.py`
**Before**:
```py
async def run(heartbeat_probe, stall_after_sec=120, check_every=30):
    age = await heartbeat_probe()
    if age <= stall_after_sec:
        last_ok = time.monotonic()
    else:
        log.error("heartbeat stale ...")
        os._exit(1)
```

**After**:
```py
async def run(
    heartbeat_probe,
    *,
    stall_after_sec: int = 120,
    check_every: int = 30,
    state_probe: Optional[StateProbe] = None,
    disconnect_grace_sec: Optional[int] = None,
    latency_probe: Optional[LatencyProbe] = None,
) -> None:
    snapshot = state_probe() if state_probe else None
    if connected and age > stall_after_sec:
        latency = latency_probe()
        if latency is None or latency > 10.0:
            os._exit(1)
    elif not connected and down_for > disconnect_limit:
        os._exit(1)
```
Key updates:
- Mirror legacy zombie-vs-disconnect decisions using connection snapshot + latency fallback.
- Accept configurable disconnect grace and log the active thresholds.

### `config/runtime.py`
**Before**:
```py
def get_watchdog_stall_sec(default: int = 120) -> int:
    return int(os.getenv("WATCHDOG_STALL_SEC", str(default)))
```

**After**:
```py
def get_keepalive_interval_sec(default_prod: int = 360, default_nonprod: int = 60) -> int:
    env = get_env_name().lower()
    fallback = default_nonprod if env in {"dev", "development", "test", "qa", "stage"} else default_prod

    override = os.getenv("KEEPALIVE_INTERVAL_SEC")
    if override is not None:
        return _coerce_int(override, fallback)

    return fallback


def get_watchdog_stall_sec(default: Optional[int] = None) -> int:
    override = os.getenv("WATCHDOG_STALL_SEC")
    if override is not None:
        fallback = default if default is not None else get_keepalive_interval_sec() * 3 + 30
        return _coerce_int(override, fallback)
    keepalive = get_keepalive_interval_sec()
    return keepalive * 3 + 30
```
Key updates:
- Introduce `KEEPALIVE_INTERVAL_SEC` defaulting to 360s (prod) / 60s (non-prod).
- Derive stall + disconnect grace defaults from keepalive cadence with env overrides.

## Deployment notes
- Set `KEEPALIVE_INTERVAL_SEC` explicitly if Render dyno needs a different cadence.
- Override `WATCHDOG_STALL_SEC` / `WATCHDOG_DISCONNECT_GRACE_SEC` when tuning restart aggressiveness.
- No HTTP self-pings were added; watchdog relies solely on gateway state + latency.
