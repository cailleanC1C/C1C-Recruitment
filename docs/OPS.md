# OPS

- Two Render web services: test and prod (same repo, different env vars)
- Health endpoints: `/ready`, `/healthz` (see contracts)
- Watchdog exits on stall; platform restarts service
