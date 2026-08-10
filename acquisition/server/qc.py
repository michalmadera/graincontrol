"""Orkiestrator QC ujęcia (§6) — miary z `qc/imageStats.py` + progi z profilu → werdykt.

`imageStats.py` dostarcza same miary (liczy, nie ocenia). Tu składamy je w
`qc.json`: każda pozycja z tabeli §6 dostaje wartość, próg, status i wartość
odniesienia z profilu. Werdykt QC jest **osobną bramką** od kontraktu metadanych
(§5, liczonego przez `captureSample`): zdjęcie ląduje w archiwum tylko gdy oba
przechodzą.

Statusy pojedynczej miary:
    ok      — w normie
    warn    — ostrzeżenie (nie blokuje zapisu)
    reject  — odrzucenie (blokuje zapis)
    skip    — brak odniesienia w profilu (np. `expected` = null, brak `focus_roi`)

Werdykt łączny: reject jeśli którakolwiek miara = reject; inaczej ok_with_warnings
jeśli jest warn; inaczej ok.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# imageStats leży w rodzeństwie acquisition/qc/ — dokładamy je do ścieżki bez
# wymuszania pakietu (katalog nie ma __init__.py).
_QC_DIR = Path(__file__).resolve().parent.parent / "qc"
if str(_QC_DIR) not in sys.path:
    sys.path.insert(0, str(_QC_DIR))
import imageStats as stats  # noqa: E402

# Progi z tabeli §6. `station.json`/profil mogą je nadpisać przez blok "qc",
# ale wartości domyślne są tożsame ze specyfikacją.
DEFAULT_THRESHOLDS = {
    "max_dn_reject": 250,          # > 250 → odrzucenie
    "clip_dn": 250,               # próg pikseli liczonych jako clip
    "patch_sd_dn": 8.0,           # sd < 8 DN → wzorzec obecny
    "patch_cover_frac": 0.90,     # > 90% ROI w paśmie ±sd → wzorzec obecny
    "patch_L_white_warn": 0.5,    # |Δ| L* > 0,5 vs expected → ostrzeżenie
    "patch_sd_L_warn": 1.5,       # sd L* > 1,5 → ostrzeżenie
    "focus_drop_reject": 0.15,    # spadek > 15% vs expected → odrzucenie
    "foreground_lo": 0.20,        # < 20% → ostrzeżenie
    "foreground_hi": 0.90,        # > 90% → ostrzeżenie
    "mean_dn_drift_warn": 0.03,   # |Δ| > 3% vs poprzednie ujęcie → ostrzeżenie
}

_RANK = {"ok": 0, "skip": 0, "warn": 1, "reject": 2}


def _thresholds(profile: dict) -> dict:
    merged = dict(DEFAULT_THRESHOLDS)
    merged.update(profile.get("qc", {}).get("thresholds", {}))
    return merged


def _check(name: str, value, threshold, status: str, reference=None,
           note: str = "") -> dict:
    return {"name": name, "value": value, "threshold": threshold,
            "status": status, "reference": reference, "note": note}


def _patch_present(rgb: np.ndarray, roi, thr: dict) -> tuple[bool, dict]:
    """Wzorzec obecny, jeśli ROI jest gładki (sd < próg) i jednorodny (>90% w paśmie).

    Materiał przysypujący wzorzec podnosi sd i psuje jednorodność — to właśnie
    ma wychwycić ta miara (§6, kotwica fotometryczna)."""
    region = stats.crop(rgb, roi, erosion=0)
    gray = stats.luma(region)
    sd = float(gray.std())
    median = float(np.median(gray))
    cover = float((np.abs(gray - median) <= thr["patch_sd_dn"]).mean())
    present = sd < thr["patch_sd_dn"] and cover >= thr["patch_cover_frac"]
    return present, {"sd_dn": round(sd, 3), "cover_frac": round(cover, 4),
                     "median_dn": round(median, 2)}


def compute_qc(rgb: np.ndarray, profile: dict,
               prev_mean_dn: float | None = None) -> dict:
    """Liczy wszystkie miary §6 i zwraca strukturę `qc.json` z werdyktem.

    `rgb` to (H, W, 3) uint8 — zawartość zapisanego PNG. `prev_mean_dn` służy
    tylko mierze dryfu `mean_dn` (poprzednie ujęcie w sesji); None → skip.
    """
    thr = _thresholds(profile)
    expected = profile.get("expected", {}) or {}
    checks: list[dict] = []

    # --- max_dn / clip_frac / mean_dn ---
    frame = stats.frame_stats(rgb, clip_dn=int(thr["clip_dn"]))
    checks.append(_check(
        "max_dn", frame["max_dn"], f"> {thr['max_dn_reject']}",
        "reject" if frame["max_dn"] > thr["max_dn_reject"] else "ok",
        reference=expected.get("max_dn")))
    checks.append(_check(
        "clip_frac", round(frame["clip_frac"], 6), "> 0",
        "reject" if frame["clip_frac"] > 0 else "ok", reference=0.0))

    if prev_mean_dn is None or prev_mean_dn == 0:
        checks.append(_check("mean_dn", round(frame["mean_dn"], 3),
                             f"|Δ| > {thr['mean_dn_drift_warn']:.0%} vs poprz.",
                             "skip", note="brak poprzedniego ujęcia w sesji"))
    else:
        drift = abs(frame["mean_dn"] - prev_mean_dn) / prev_mean_dn
        checks.append(_check(
            "mean_dn", round(frame["mean_dn"], 3),
            f"|Δ| > {thr['mean_dn_drift_warn']:.0%}",
            "warn" if drift > thr["mean_dn_drift_warn"] else "ok",
            reference=round(prev_mean_dn, 3),
            note=f"Δ = {drift:+.2%}"))

    # --- wzorce fotometryczne (patch_present / patch_L_white / patch_sd_L) ---
    patches_out = []
    for patch in profile.get("reference_patches", []):
        name, roi = patch["name"], patch["roi"]
        present, detail = _patch_present(rgb, roi, thr)
        checks.append(_check(
            f"patch_present[{name}]", present, f"sd<{thr['patch_sd_dn']} & "
            f"cover>{thr['patch_cover_frac']:.0%}",
            "ok" if present else "reject", note=str(detail)))

        pstat = stats.patch_stats(rgb, roi) if present else None
        patches_out.append({"name": name, "roi": list(roi),
                            "present": present, "detail": detail,
                            "lab": pstat})

        if name == "white" and present and pstat is not None:
            ref_L = expected.get("white_patch_L")
            if ref_L is None:
                checks.append(_check("patch_L_white", round(pstat["L_median"], 3),
                                     f"|Δ| > {thr['patch_L_white_warn']}", "skip",
                                     note="brak expected.white_patch_L w profilu"))
            else:
                d = abs(pstat["L_median"] - ref_L)
                checks.append(_check(
                    "patch_L_white", round(pstat["L_median"], 3),
                    f"|Δ| > {thr['patch_L_white_warn']}",
                    "warn" if d > thr["patch_L_white_warn"] else "ok",
                    reference=ref_L, note=f"Δ = {pstat['L_median'] - ref_L:+.3f}"))
            checks.append(_check(
                "patch_sd_L", round(pstat["L_sd"], 3),
                f"> {thr['patch_sd_L_warn']}",
                "warn" if pstat["L_sd"] > thr["patch_sd_L_warn"] else "ok"))

    # --- ostrość (focus_metric) ---
    focus_roi = profile.get("focus_roi")
    ref_focus = expected.get("focus_metric")
    if focus_roi is None:
        checks.append(_check("focus_metric", None, f"spadek > "
                             f"{thr['focus_drop_reject']:.0%}", "skip",
                             note="brak focus_roi w profilu (§6)"))
        focus_value = None
    else:
        focus_value = stats.laplacian_variance(stats.luma(stats.crop(rgb, focus_roi)))
        if ref_focus is None:
            checks.append(_check("focus_metric", round(focus_value, 2),
                                 f"spadek > {thr['focus_drop_reject']:.0%}", "skip",
                                 reference=None,
                                 note="brak expected.focus_metric (do zmierzenia)"))
        else:
            drop = (ref_focus - focus_value) / ref_focus if ref_focus else 0.0
            checks.append(_check(
                "focus_metric", round(focus_value, 2),
                f"spadek > {thr['focus_drop_reject']:.0%}",
                "reject" if drop > thr["focus_drop_reject"] else "ok",
                reference=ref_focus, note=f"spadek = {drop:+.1%}"))

    # --- foreground_frac ---
    gray_full = stats.luma(rgb)
    otsu = stats.otsu_threshold(gray_full)
    fg = float((gray_full > otsu).mean())
    fg_status = ("warn" if (fg < thr["foreground_lo"] or fg > thr["foreground_hi"])
                 else "ok")
    checks.append(_check("foreground_frac", round(fg, 4),
                         f"< {thr['foreground_lo']:.0%} lub > {thr['foreground_hi']:.0%}",
                         fg_status, note=f"otsu = {otsu:.0f} DN"))

    status = max((c["status"] for c in checks), key=lambda s: _RANK[s])
    verdict = {"ok": "ok", "warn": "ok_with_warnings", "reject": "rejected",
               "skip": "ok"}[status]
    reject_reasons = [c["name"] for c in checks if c["status"] == "reject"]
    warnings = [c["name"] for c in checks if c["status"] == "warn"]

    return {
        "status": verdict,
        "reject_reasons": reject_reasons,
        "warnings": warnings,
        "frame": frame,
        "patches": patches_out,
        "focus_metric": focus_value,
        "foreground_frac": fg,
        "checks": checks,
    }


def qc_from_png(path: str | Path, profile: dict,
                prev_mean_dn: float | None = None) -> dict:
    """Wczytuje PNG i liczy QC — wersja używana po ujęciu przez serwer."""
    return compute_qc(stats.load_rgb(path), profile, prev_mean_dn=prev_mean_dn)
