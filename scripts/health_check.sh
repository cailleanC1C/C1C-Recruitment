#!/usr/bin/env bash
set -euo pipefail
curl -sSf http://localhost:${HEALTH_PORT:-8080}/healthz || true
