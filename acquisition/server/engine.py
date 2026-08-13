"""Most do silnika CLI — GUI robi zdjęcia dokładnie tym samym kodem co `captureSample.py`.

Druga implementacja budowania linii polecenia albo weryfikacji kontraktu prędzej czy
później rozjedzie się z pierwszą, a wtedy materiał zebrany przez GUI przestanie się
składać z materiałem zebranym z CLI — czyli dokładnie to, czemu zapobiega zasada
nadrzędna z `spec-akwizycji.md` §0. Stąd import zamiast kopii.

`acquisition/` nie jest pakietem (brak `__init__.py` w `capture/`), więc ścieżkę
dokładamy ręcznie. Po ewentualnym uporządkowaniu repozytorium w pakiety ten plik
sprowadzi się do zwykłego importu.
"""
from __future__ import annotations

import sys
from pathlib import Path

_CAPTURE_DIR = Path(__file__).resolve().parents[1] / "capture"
if str(_CAPTURE_DIR) not in sys.path:
    sys.path.insert(0, str(_CAPTURE_DIR))

import captureSample as cli   # noqa: E402  (po ustawieniu sys.path)

AcquisitionError = cli.AcquisitionError

# Funkcje silnika używane przez serwer. Lista jest jawna, żeby było widać, co
# dokładnie jest współdzielone z torem CLI.
build_command = cli.build_command
verify_contract = cli.verify_contract
enrich_meta = cli.enrich_meta
load_profile = cli.load_profile
verify_tuning_file = cli.verify_tuning_file
tool_versions = cli.tool_versions
sha256_file = cli.sha256_file
read_json = cli.read_json
write_json = cli.write_json
fsync_dir = cli.fsync_dir
now_iso = cli.now_iso
now_stamp = cli.now_stamp
