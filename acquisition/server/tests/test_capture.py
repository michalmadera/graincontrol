"""Test przepływu prostej akwizycji (atrapa kamery, bez Pi).

Sesja → etykieta BAD → 3 zdjęcia → etykieta NICE → 2 zdjęcia. Sprawdza strukturę
folderów, numerację i to, że powstają PNG + DNG + miniatury.

Uruchomienie:  python3 acquisition/server/tests/test_capture.py
"""
from __future__ import annotations

import asyncio
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

    ctrl = CaptureController(load_config())
    st = ctrl.start_session()
    assert st["session"].startswith("sesja_"), st
    session_dir = Path(st["session_path"])

    ctrl.set_label("BAD")
    for _ in range(3):
        r = await ctrl.shoot()
    assert r["index"] == 3, r
    ctrl.set_label("NICE")
    for _ in range(2):
        r = await ctrl.shoot()
    assert r["index"] == 2, r

    counts = ctrl.state()["counts"]
    assert counts == {"BAD": 3, "NICE": 2}, counts

    for name, n in (("BAD", 3), ("NICE", 2)):
        for i in range(1, n + 1):
            png = session_dir / name / f"{name}_{i}.png"
            dng = session_dir / name / f"{name}_{i}.dng"
            thumb = session_dir / ".thumb" / f"{name}_{i}.jpg"
            assert png.exists(), f"brak {png}"
            assert dng.exists(), f"brak {dng}"
            assert thumb.exists(), f"brak miniatury {thumb}"

    print(f"  sesja: {session_dir.name}")
    print(f"  BAD/  → {sorted(p.name for p in (session_dir / 'BAD').glob('*'))}")
    print(f"  NICE/ → {sorted(p.name for p in (session_dir / 'NICE').glob('*'))}")
    print(f"  liczniki: {counts}")

    # ponowne wejście w BAD kontynuuje numerację (bad_4)
    ctrl.set_label("BAD")
    r = await ctrl.shoot()
    assert r["index"] == 4, r
    print(f"  powrót do BAD → {r['png']} (numeracja ciągła)")
    print("OK — przepływ sesja→etykieta→zdjęcia (PNG+DNG) działa.")
    return 0


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        return asyncio.run(_run(Path(tmp)))


if __name__ == "__main__":
    sys.exit(main())
