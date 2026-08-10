#!/usr/bin/env bash
# Uruchamia UI akwizycji na maszynie deweloperskiej (bez Pi), z atrapą kamery.
# Generuje fixtures (stanowisko + atrapa rpicam-still), startuje FastAPI + bundle
# React. Otwórz potem http://127.0.0.1:8000 — zobaczysz ekran sesji i cały przepływ
# (start sesji -> deklaracja próbki -> ZRÓB ZDJĘCIE -> werdykt QC).
#
#   acquisition/server/run-dev.sh            # port 8000
#   PORT=8100 acquisition/server/run-dev.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACQ="$(dirname "$HERE")"
REPO="$(dirname "$ACQ")"
PORT="${PORT:-8000}"
FIX="${FIX:-$REPO/.dev-fixtures}"

echo "» generuję fixtures deweloperskie w $FIX"
STATION="$(python3 "$HERE/dev_fixtures.py" "$FIX")"
echo "» station: $STATION"
echo "» UI:      http://127.0.0.1:$PORT"
echo

export GRAINCONTROL_STATION="$STATION"
export PYTHONPATH="$ACQ"
exec python3 -m uvicorn server.main:app --host 127.0.0.1 --port "$PORT" --workers 1
