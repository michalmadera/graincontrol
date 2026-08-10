"""Test orkiestratora QC (§6) na syntetycznych kadrach — bez kamery.

Sprawdza, że progi z tabeli §6 przekładają się na właściwy status i werdykt:
czysty kadr → ok, przesterowanie → rejected, przysypany wzorzec → rejected.
Uruchomienie:  python3 acquisition/server/tests/test_qc.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from server import qc  # noqa: E402

# Profil czytamy z repo, żeby ROI wzorców były rzeczywiste.
_PROFILE_PATH = (Path(__file__).resolve().parents[3]
                 / "profiles" / "acquisition" / "P1-scientific-20260810.json")
PROFILE = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
H, W = PROFILE["resolution"][1], PROFILE["resolution"][0]


def _base_frame(rng) -> np.ndarray:
    """Kadr bazowy: teksturowane tło ~55% foreground + gładkie wzorce z profilu."""
    frame = rng.integers(40, 130, size=(H, W, 3), dtype=np.uint8)
    # jaśniejsze "ziarna", żeby foreground_frac wpadł w normę (nie <20%, nie >90%)
    mask = rng.random((H, W)) < 0.55
    frame[mask] = rng.integers(150, 210, size=(int(mask.sum()), 3), dtype=np.uint8)
    for patch, level in (("white", 205), ("grey", 120)):
        x, y, w, h = next(p["roi"] for p in PROFILE["reference_patches"]
                          if p["name"] == patch)
        frame[y:y + h, x:x + w] = np.clip(
            level + rng.integers(-2, 3, size=(h, w, 3)), 0, 255).astype(np.uint8)
    return frame


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _status_of(result, name):
    return next(c["status"] for c in result["checks"] if c["name"] == name)


def main() -> int:
    rng = np.random.default_rng(0)  # deterministyczny — brak Math.random w scenach

    clean = _base_frame(rng)
    r = qc.compute_qc(clean, PROFILE)
    _assert(r["status"] in ("ok", "ok_with_warnings"), f"czysty: {r['status']}")
    _assert(_status_of(r, "max_dn") == "ok", "czysty max_dn")
    _assert(_status_of(r, "clip_frac") == "ok", "czysty clip")
    _assert(_status_of(r, "patch_present[white]") == "ok", "czysty biel obecna")
    _assert(_status_of(r, "patch_present[grey]") == "ok", "czysty szarość obecna")
    print(f"  czysty kadr           → {r['status']:16} (fg={r['foreground_frac']:.2f})")

    clipped = clean.copy()
    clipped[100:400, 100:400] = 255  # przesterowanie
    r = qc.compute_qc(clipped, PROFILE)
    _assert(r["status"] == "rejected", f"przesterowany: {r['status']}")
    _assert("max_dn" in r["reject_reasons"], "przesterowany max_dn reject")
    _assert("clip_frac" in r["reject_reasons"], "przesterowany clip reject")
    print(f"  przesterowany kadr    → {r['status']:16} {r['reject_reasons']}")

    covered = clean.copy()
    x, y, w, h = next(p["roi"] for p in PROFILE["reference_patches"]
                      if p["name"] == "white")
    covered[y:y + h, x:x + w] = rng.integers(30, 220, size=(h, w, 3), dtype=np.uint8)
    r = qc.compute_qc(covered, PROFILE)
    _assert(r["status"] == "rejected", f"przysypany wzorzec: {r['status']}")
    _assert("patch_present[white]" in r["reject_reasons"], "przysypany biel reject")
    print(f"  przysypany wzorzec    → {r['status']:16} {r['reject_reasons']}")

    # dryf mean_dn względem poprzedniego ujęcia → ostrzeżenie
    r = qc.compute_qc(clean, PROFILE, prev_mean_dn=r["frame"]["mean_dn"] * 1.2)
    _assert(_status_of(r, "mean_dn") == "warn", "dryf mean_dn warn")
    print(f"  dryf mean_dn +ostrzeż → {_status_of(r, 'mean_dn')}")

    print("OK — wszystkie asercje QC §6 przeszły.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
