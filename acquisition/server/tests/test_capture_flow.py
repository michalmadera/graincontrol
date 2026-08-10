"""Test integracyjny: sesja → próbka → ujęcie → QC przez prawdziwy `captureSample.py`.

Bez Pi. Używa fixtures deweloperskich (`server.dev_fixtures`): atrapa `rpicam-still`
emituje syntetyczny PNG z wzorcami + metadane kontraktu §5. Dowodzi, że integracja
subprocess-first działa: kontrakt przechodzi, ujęcie ląduje w `captures/`, a QC §6
liczy się z zapisanego kadru.

Uruchomienie:  python3 acquisition/server/tests/test_capture_flow.py
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from server.config import load_config            # noqa: E402
from server.capture_engine import CaptureEngine  # noqa: E402
from server.dev_fixtures import write_fixtures    # noqa: E402
from server import qc                             # noqa: E402


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
        return asyncio.run(_run(write_fixtures(Path(tmp))))


if __name__ == "__main__":
    sys.exit(main())
