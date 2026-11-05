#!/usr/bin/env bash
# Backend na atrapach, czas ~50× szybciej, dane w katalogu tymczasowym.
set -euo pipefail
TUTAJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$TUTAJ/../../.." && pwd)"
export STACJA_MASZYNA=symulator STACJA_TEMPO="${STACJA_TEMPO:-0.02}"
export STACJA_DANE="$(mktemp -d)"
export PYTHONPATH="$REPO/station"
exec "$REPO/.venv/bin/python" -m uvicorn stacja.main:app --host 127.0.0.1 --port "${PORT:-8101}" --log-level warning
