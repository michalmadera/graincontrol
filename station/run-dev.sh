#!/usr/bin/env bash
# Stacja na atrapach na zwykłym komputerze. UI: http://127.0.0.1:8100
set -euo pipefail
TUTAJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$TUTAJ")"
export STACJA_MASZYNA="${STACJA_MASZYNA:-symulator}" STACJA_TEMPO="${STACJA_TEMPO:-0.2}"
export GRAINCONTROL_DUMMY="${GRAINCONTROL_DUMMY:-1}"
export STACJA_SERWIS="${STACJA_SERWIS:-http://127.0.0.1:8102}"

# Serwis analizy na atrapie, żeby całość działała jednym poleceniem.
ANALIZA_DANE="$TUTAJ/data/serwis" ANALIZA_OPOZNIENIE_S="${ANALIZA_OPOZNIENIE_S:-3}" PYTHONPATH="$REPO/service" \
  "$REPO/.venv/bin/python" -m uvicorn analiza.main:create_app --factory --host 127.0.0.1 --port 8102 --log-level warning &
SERWIS=$!
trap 'kill "$SERWIS" 2>/dev/null || true' EXIT

echo "UI: http://127.0.0.1:${PORT:-8100}"
PYTHONPATH="$TUTAJ" "$REPO/.venv/bin/python" -m uvicorn stacja.main:create_app --factory --host 127.0.0.1 --port "${PORT:-8100}"
