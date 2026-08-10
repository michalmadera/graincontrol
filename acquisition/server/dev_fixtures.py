"""Fixtures deweloperskie: stanowisko z atrapą kamery — do uruchomienia UI bez Pi.

Buduje `station.json` + profil + atrapę `rpicam-still` (emituje syntetyczny PNG z
wzorcami i metadane kontraktu §5), tak że cały przepływ sesja→próbka→ujęcie→QC
działa na maszynie deweloperskiej. Używane przez `run-dev.sh` i test integracyjny.

    python3 acquisition/server/dev_fixtures.py [KATALOG]   # wypisze ścieżkę station.json
"""
from __future__ import annotations

import hashlib
import json
import stat
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BASE_PROFILE = json.loads(
    (REPO / "profiles" / "acquisition" / "P1-scientific-20260810.json").read_text())

RPICAM_STUB = r'''#!/usr/bin/env python3
"""Atrapa rpicam-still: syntetyczny PNG z wzorcami + metadane kontraktu."""
import json, sys
import numpy as np
from PIL import Image

args = sys.argv[1:]
if "--version" in args or "--help" in args:
    print("rpicam-still (STUB) 0.0"); sys.exit(0)

def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default

out = opt("-o"); meta = opt("--metadata")
w, h = int(opt("--width", "4056")), int(opt("--height", "3040"))
shutter = float(opt("--shutter", "65000"))
gain = float(opt("--gain", "1.0"))
red, blue = (float(x) for x in opt("--awbgains", "2.36,2.19").split(","))

rng = np.random.default_rng()
img = rng.integers(45, 125, size=(h, w, 3), dtype=np.uint8)
mask = rng.random((h, w)) < 0.55
img[mask] = rng.integers(150, 210, size=(int(mask.sum()), 3), dtype=np.uint8)
for x0, y0, ww, hh, lv in ((3527, 2511, 418, 418, 205), (3527, 2009, 418, 418, 120)):
    img[y0:y0+hh, x0:x0+ww] = np.clip(lv + rng.integers(-2, 3, (hh, ww, 3)), 0, 255)
Image.fromarray(img).save(out)

if meta:
    json.dump({
        "ExposureTime": shutter, "AnalogueGain": gain, "DigitalGain": 1.0,
        "ColourGains": [red, blue], "Lux": 120.0,
        "ColourCorrectionMatrix": [1.8, -0.6, -0.2, -0.3, 1.6, -0.3, 0.0, -0.5, 1.5],
        "SensorTimestamp": 0,
    }, open(meta, "w"))
'''


def write_fixtures(root: Path) -> Path:
    """Tworzy w `root` atrapę, profil i station.json; zwraca ścieżkę station.json."""
    root.mkdir(parents=True, exist_ok=True)

    tuning = root / "tuning.json"
    tuning.write_text('{"version": 2.0, "STUB": true}\n')
    tuning_sha = hashlib.sha256(tuning.read_bytes()).hexdigest()

    stub = root / "rpicam-still-stub.py"
    stub.write_text(RPICAM_STUB)
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

    profile = dict(BASE_PROFILE)
    profile["tuning_file"] = str(tuning)
    profile["tuning_file_sha256"] = tuning_sha
    profile["calibration"] = {"flatfield_id": None, "scale_id": None, "colorchart_id": None}
    (root / "profile-dev.json").write_text(json.dumps(profile))

    station = {
        "archive_root": str(root / "archiwum"),
        "profile_path": str(root / "profile-dev.json"),
        "rpicam_still": str(stub),
        "operator": "DEV", "illuminator_id": "STUB",
        "min_free_captures": 1, "bytes_per_capture": 1024,
        "camera_backend": "dummy",
        "study": {
            "study_id": "DEV-demo",
            "verdicts": ["OK", "NOK", "graniczny", "nieoceniony"],
            "protocol_stages": ["A", "B", "C", "D", "E", "F", "inne"],
            "verdict_reasons_vocabulary": [
                "za_ciemny", "kremowy", "zazolcony", "zabrudzony",
                "nieregularny_ksztalt", "zla_frakcja", "obcy_material"],
        },
    }
    station_path = root / "station-dev.json"
    station_path.write_text(json.dumps(station))
    return station_path


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / ".dev-fixtures"
    print(write_fixtures(target))
