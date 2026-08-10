#!/usr/bin/env bash
# Uruchamia narzędzie akwizycji na maszynie deweloperskiej (bez Pi), z atrapą kamery.
# Zdjęcia (syntetyczne) lądują w dane/ tak jak na Pi. Otwórz http://127.0.0.1:8000
#
#   acquisition/server/run-dev.sh            # port 8000, atrapa
#   PORT=8100 acquisition/server/run-dev.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACQ="$(dirname "$HERE")"
PORT="${PORT:-8000}"

export GRAINCONTROL_DUMMY="${GRAINCONTROL_DUMMY:-1}"   # atrapa kamery na dev
export PYTHONPATH="$ACQ"

echo "» atrapa kamery: GRAINCONTROL_DUMMY=$GRAINCONTROL_DUMMY"
echo "» UI: http://127.0.0.1:$PORT"
echo
exec python3 -m uvicorn server.main:app --host 127.0.0.1 --port "$PORT"
