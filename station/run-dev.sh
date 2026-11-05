#!/usr/bin/env bash
# Stacja na atrapach na zwykłym komputerze. UI: http://127.0.0.1:8100
set -euo pipefail
TUTAJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$TUTAJ")"
export STACJA_MASZYNA="${STACJA_MASZYNA:-symulator}" STACJA_TEMPO="${STACJA_TEMPO:-0.2}"
export PYTHONPATH="$TUTAJ"
exec "$REPO/.venv/bin/python" -m uvicorn stacja.main:app --host 127.0.0.1 --port "${PORT:-8100}"
