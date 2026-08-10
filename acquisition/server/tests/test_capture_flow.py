"""Test integracyjny: sesja → próbka → ujęcie → QC przez prawdziwy `captureSample.py`.

Bez Pi. Buduje w katalogu tymczasowym: atrapę `rpicam-still` (emituje syntetyczny
PNG z wzorcami + metadane kontraktu §5), profil i `station.json` dopięte do atrapy,
po czym przepuszcza cały przepływ przez owijkę serwera. Dowodzi, że integracja
subprocess-first działa: kontrakt przechodzi, ujęcie ląduje w `captures/`, a QC §6
liczy się z zapisanego kadru.

Uruchomienie:  python3 acquisition/server/tests/test_capture_flow.py
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from server.config import load_config          # noqa: E402
from server.capture_engine import CaptureEngine  # noqa: E402
from server import qc                            # noqa: E402

REPO = Path(__file__).resolve().parents[3]
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

rng = np.random.default_rng(1)
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


def _write_fixtures(root: Path) -> Path:
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
    profile_path = root / "profile-test.json"
    profile_path.write_text(json.dumps(profile))

    station = {
        "archive_root": str(root / "archiwum"),
        "profile_path": str(profile_path),
        "rpicam_still": str(stub),   # plik wykonywalny z shebangiem (nie 'python stub')
        "operator": "TEST", "illuminator_id": "STUB",
        "min_free_captures": 1, "bytes_per_capture": 1024,
        "study": {
            "study_id": "T-test", "verdicts": ["OK", "NOK", "graniczny", "nieoceniony"],
            "protocol_stages": ["A", "B", "C", "D", "E", "F", "inne"],
            "verdict_reasons_vocabulary": ["kremowy", "zazolcony"],
        },
    }
    station_path = root / "station-test.json"
    station_path.write_text(json.dumps(station))
    return station_path


async def _run(station_path: Path) -> int:
    config = load_config(station_path)
    engine = CaptureEngine(config)

    decl = await engine.declare_sample(
        batch="D-001", sample="S-01", supplier="ACME", material="kruszywo 8/16",
        verdict="OK", verdict_author="TEST", stage="inne", no_calibration=True)
    assert decl.ok, f"deklaracja: {decl.stderr or decl.stdout}"

    cap = await engine.capture()
    assert cap.ok, f"ujęcie: exit={cap.exit_code} {cap.stderr or cap.stdout}"

    row = engine.last_manifest_row()
    assert row and row["contract_status"] == "ok", f"kontrakt: {row}"
    cap_dir = engine.capture_dir(row["capture_id"])
    assert cap_dir and (cap_dir / "capture.png").exists(), "brak capture.png w captures/"
    print(f"  ujęcie {row['capture_id']} → contract_status={row['contract_status']}")

    r = qc.qc_from_png(cap_dir / "capture.png", config.profile)
    assert r["status"] in ("ok", "ok_with_warnings"), f"QC: {r['status']} {r['reject_reasons']}"
    print(f"  QC §6 z zapisanego kadru → {r['status']} (fg={r['foreground_frac']:.2f})")

    end = await engine.end_session()
    assert end.ok, f"zamknięcie: {end.stderr}"
    print("OK — przepływ sesja→próbka→ujęcie→QC działa przez prawdziwy silnik.")
    return 0


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        return asyncio.run(_run(_write_fixtures(Path(tmp))))


if __name__ == "__main__":
    sys.exit(main())
