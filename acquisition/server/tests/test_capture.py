"""Test przepływu akwizycji z GUI (atrapa kamery, bez Pi).

Sprawdza to, co odróżnia ten tor od zwykłego zapisu plików:

  * ta sama linia polecenia co w CLI — z pliku strojenia z profilu, `--metadata`,
    `--raw` i `--immediate`,
  * kontrakt akwizycji §5 liczony po każdym ujęciu,
  * komplet plików towarzyszących: metadane wzbogacone o `_isp_*`/`_command_line`,
    rekord akwizycji, suma kontrolna,
  * ujęcie niezgodne z profilem → `odrzucone/`, **bez** zwiększenia numeru,
  * zapis przerwany → przy starcie sesji trafia do `odrzucone/niedokonczone/`.

Uruchomienie:  python3 acquisition/server/tests/test_capture.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


async def _run(data_root: Path) -> int:
    os.environ["GRAINCONTROL_DUMMY"] = "1"
    os.environ["GRAINCONTROL_DANE"] = str(data_root)
    from server.config import load_config
    from server.capture import CaptureController

    config = load_config()
    assert config.blocking_error is None, config.blocking_error
    assert config.profile_id == "P2-scientific-20260813", config.profile_id
    print(f"  profil: {config.profile_id}, {config.profile['shutter_us']} µs")

    ctrl = CaptureController(config)
    st = ctrl.start_session()
    assert st["session"].startswith("sesja_"), st
    session_dir = Path(st["session_path"])

    ctrl.set_label("BAD")
    for _ in range(3):
        r = await ctrl.shoot()
    assert r["index"] == 3 and r["accepted"], r
    ctrl.set_label("NICE")
    for _ in range(2):
        r = await ctrl.shoot()
    assert r["index"] == 2 and r["accepted"], r

    counts = ctrl.state()["counts"]
    assert counts == {"BAD": 3, "NICE": 2}, counts

    for name, n in (("BAD", 3), ("NICE", 2)):
        for i in range(1, n + 1):
            stem = f"{name}_{i}"
            for suffix in (".png", ".dng", "_meta.json", "_acquisition.json", ".sha256"):
                path = session_dir / name / f"{stem}{suffix}"
                assert path.exists(), f"brak {path}"
            assert (session_dir / ".thumb" / f"{stem}.jpg").exists(), stem

    # --- linia polecenia i wzbogacenie metadanych: to samo, co robi CLI
    meta = json.loads((session_dir / "BAD" / "BAD_1_meta.json").read_text())
    for key in ("_isp_sharpness", "_isp_denoise", "_tuning_file", "_profile_id",
                "_command_line", "_rpicam_version"):
        assert key in meta, f"brak {key} w meta.json"
    cmd = " ".join(meta["_command_line"])
    for flag in ("--tuning-file", "--metadata", "--metadata-format", "--raw",
                 "--immediate", "--sharpness", "--denoise", "--awbgains"):
        assert flag in cmd, f"linia polecenia bez {flag}"
    assert meta["_dummy"] is True, "ujęcie z atrapy musi być oznaczone"
    assert str(config.profile["shutter_us"]) in cmd, cmd
    print(f"  metadane wzbogacone o {sum(k.startswith('_') for k in meta)} pól '_'")

    record = json.loads((session_dir / "BAD" / "BAD_1_acquisition.json").read_text())
    assert record["contract"]["status"] == "ok", record["contract"]
    fields = {c["field"] for c in record["contract"]["checks"]}
    assert {"ExposureTime", "AnalogueGain", "DigitalGain",
            "ColourCorrectionMatrix"} <= fields, fields
    print(f"  kontrakt sprawdza: {', '.join(sorted(fields))}")

    # --- sumy kontrolne zgadzają się z plikami na dysku
    import hashlib
    for line in (session_dir / "BAD" / "BAD_1.sha256").read_text().splitlines():
        digest, name = line.split("  ")
        actual = hashlib.sha256((session_dir / "BAD" / name).read_bytes()).hexdigest()
        assert actual == digest, f"suma {name} nie zgadza się"
    print("  sumy kontrolne zgodne z plikami")

    # --- ujęcie niezgodne z profilem: odrzucone, numer bez zmian
    ctrl.set_label("BAD")
    original = ctrl.reference["reference_ccm"]
    ctrl.reference["reference_ccm"] = [9.0] * 9        # symulacja zmiany CCM w sesji
    r = await ctrl.shoot()
    assert r["accepted"] is False, r
    assert r["contract"] == "rejected" and r["violations"], r
    assert (session_dir / "odrzucone" / "BAD" / f"{r['png']}").exists(), r
    print(f"  odrzucone: {r['violations'][0][:60]}…")

    ctrl.reference["reference_ccm"] = original
    r2 = await ctrl.shoot()
    assert r2["accepted"] and r2["index"] == r["index"], (r, r2)
    print(f"  powtórka po odrzuceniu ma ten sam numer: {r2['png']}")

    # --- manifest i dziennik
    manifest = (session_dir / "manifest.csv").read_text().splitlines()
    assert len(manifest) == 1 + 7, manifest          # nagłówek + 5 + odrzucone + powtórka
    events = [json.loads(x)["event"] for x in
              (session_dir / "journal.jsonl").read_text().splitlines()]
    assert events.count("capture_rejected") == 1 and events.count("capture_accepted") == 6, events
    print(f"  manifest: {len(manifest) - 1} wierszy, dziennik: {len(events)} zdarzeń")

    # --- zapis przerwany zanikiem zasilania
    broken = session_dir / ".tmp" / "BAD_99"
    broken.mkdir(parents=True)
    (broken / "BAD_99.png").write_bytes(b"niedokonczone")
    ctrl2 = CaptureController(config)
    ctrl2.session_dir, ctrl2.session_id = session_dir, session_dir.name
    recovered = ctrl2._recover_interrupted()
    assert recovered == ["BAD_99"], recovered
    assert (session_dir / "odrzucone" / "niedokonczone" / "BAD_99" / "BAD_99.png").exists()
    print("  przerwany zapis przeniesiony do odrzucone/niedokonczone/")

    print("OK — GUI zapisuje tym samym silnikiem co CLI.")
    return 0


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        return asyncio.run(_run(Path(tmp)))


if __name__ == "__main__":
    sys.exit(main())
