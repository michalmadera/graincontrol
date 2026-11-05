#!/usr/bin/env bash
# Serwis analizy na atrapie, z krótkim czasem analizy i sterowaniem do testów.
set -euo pipefail
TUTAJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$TUTAJ/../../.." && pwd)"
export ANALIZA_DANE="$(mktemp -d)" ANALIZA_OPOZNIENIE_S="${ANALIZA_OPOZNIENIE_S:-1}" ANALIZA_DEV=1
export PYTHONPATH="$REPO/service"
exec "$REPO/.venv/bin/python" -m uvicorn analiza.main:create_app --factory --host 127.0.0.1 --port "${PORT:-8106}" --log-level warning
