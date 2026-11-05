#!/usr/bin/env bash
# Backend na atrapach, czas ~50× szybciej, dane w katalogu tymczasowym.
set -euo pipefail
TUTAJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$TUTAJ/../../.." && pwd)"
export STACJA_MASZYNA="${STACJA_MASZYNA_E2E:-symulator}" STACJA_TEMPO="${STACJA_TEMPO:-0.02}"
export STACJA_DANE="${STACJA_DANE_STALE:-$(mktemp -d)}"
export GRAINCONTROL_DUMMY="${GRAINCONTROL_DUMMY:-1}"
export STACJA_SERWIS="${STACJA_SERWIS:-http://127.0.0.1:8102}"
export STACJA_ATRAPA_KAMERY="${STACJA_ATRAPA_KAMERY:-1}"
export PYTHONPATH="$REPO/station"
exec "$REPO/.venv/bin/python" -m uvicorn stacja.main:create_app --factory --host 127.0.0.1 --port "${PORT:-8101}" --log-level warning
