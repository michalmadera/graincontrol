#!/usr/bin/env python3
"""Skala mm/px z wzorca wymiaru w płaszczyźnie materiału (§7).

Dziś `analiza/an3.py` przyjmuje 35,9 µm/px jako **założenie** (12 mm z 290 mm), nie
pomiar. Każda wielkość ziarna w milimetrach dziedziczy ten błąd, więc dopóki wzorzec nie
zostanie sfotografowany, metryki kształtu są wyłącznie w pikselach.

Praca w dwóch krokach, bo odczyt współrzędnych wymaga oka operatora:

    scaleMeasure.py -c station.json --shoot
        zdjęcie linijki + preview_grid.png: podgląd z siatką opisaną we współrzędnych
        pełnej rozdzielczości

    scaleMeasure.py -c station.json --calib scale_20260810-1204 \\
        --pair 812,1455,3620,1461,100 --pair 830,2100,3640,2106,100
        każda para to x1,y1,x2,y2,odległość_mm

Podawaj **kilka par** na różnych wysokościach kadru. Rozrzut między nimi jest miarą
dokładności wskazania i skośności ustawienia kamery — przy jednej parze ten błąd
pozostaje nieznany, a nie zniknięty.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import calibCommon as common
from calibCommon import acq, stats

PREVIEW_DIVISOR = 4
GRID_STEP_PX = 200
SPREAD_WARN = 0.005


def write_preview_grid(image_path: Path, target: Path) -> None:
    """Podgląd z siatką opisaną we współrzędnych pełnego kadru."""
    rgb = stats.load_rgb(image_path)
    height, width = rgb.shape[:2]
    preview = Image.fromarray(rgb[::PREVIEW_DIVISOR, ::PREVIEW_DIVISOR])
    draw = ImageDraw.Draw(preview)
    for x in range(0, width, GRID_STEP_PX):
        draw.line([(x // PREVIEW_DIVISOR, 0), (x // PREVIEW_DIVISOR, preview.height)],
                  fill=(255, 0, 255), width=1)
        if x % (GRID_STEP_PX * 2) == 0:
            draw.text((x // PREVIEW_DIVISOR + 2, 2), str(x), fill=(255, 0, 255))
    for y in range(0, height, GRID_STEP_PX):
        draw.line([(0, y // PREVIEW_DIVISOR), (preview.width, y // PREVIEW_DIVISOR)],
                  fill=(255, 0, 255), width=1)
        if y % (GRID_STEP_PX * 2) == 0:
            draw.text((2, y // PREVIEW_DIVISOR + 2), str(y), fill=(255, 0, 255))
    preview.save(target)


def parse_pair(text: str) -> dict:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 5:
        raise common.AcquisitionError(
            f"Para '{text}' ma mieć postać x1,y1,x2,y2,odległość_mm")
    x1, y1, x2, y2 = (int(float(p)) for p in parts[:4])
    millimetres = float(parts[4])
    if millimetres <= 0:
        raise common.AcquisitionError(f"Para '{text}': odległość musi być dodatnia")
    distance = math.hypot(x2 - x1, y2 - y1)
    if distance < 1:
        raise common.AcquisitionError(f"Para '{text}': punkty się pokrywają")
    return {
        "p1": [x1, y1], "p2": [x2, y2], "distance_mm": millimetres,
        "distance_px": round(distance, 2),
        "mm_per_px": millimetres / distance,
        "um_per_px": millimetres * 1000.0 / distance,
        "angle_deg": round(math.degrees(math.atan2(y2 - y1, x2 - x1)), 2),
    }


def shoot(station, profile, profile_sha, tuning_sha, study_dir) -> int:
    calib_id, directory = common.new_calib_dir(study_dir, "scale")
    print("Połóż linijkę w płaszczyźnie materiału, płasko, przez cały kadr.\n")
    reference = {"reference_ccm": None, "reference_lux": None}
    image, meta, command = common.capture_into(station, profile, directory, "ruler")
    violations = common.contract_violations(meta, profile, reference)
    write_preview_grid(image, directory / "preview_grid.png")
    common.finish(study_dir, "scale", calib_id, directory, {
        "profile_id": profile["profile_id"],
        "profile_sha256": profile_sha,
        "tuning_file_sha256": tuning_sha,
        "status": "oczekuje na wskazanie punktów",
        "contract_violations": violations,
        "command_line": command,
    })
    print(f"Zapisano {directory}")
    print(f"  podgląd z siatką: {directory / 'preview_grid.png'}")
    print("\nOdczytaj z podglądu współrzędne dwóch kresek linijki (siatka jest opisana")
    print("we współrzędnych pełnego kadru, kreska co 200 px) i uruchom:")
    print(f"  scaleMeasure.py -c <config> --calib {calib_id} \\")
    print("      --pair x1,y1,x2,y2,odległość_mm --pair …")
    if violations:
        print("\nUWAGA — kontrakt: " + "; ".join(violations))
    return 0


def measure(study_dir, profile, calib_id: str, pairs: list[str]) -> int:
    directory = study_dir / "calib" / calib_id
    if not directory.exists():
        raise common.AcquisitionError(f"Nie ma ujęcia kalibracyjnego {calib_id}")
    measurements = [parse_pair(text) for text in pairs]
    values = np.array([m["um_per_px"] for m in measurements])
    mean = float(values.mean())
    spread = float(values.max() - values.min()) / mean if len(values) > 1 else 0.0

    record = acq.read_json(directory / "calib.json")
    record.update({
        "status": "zmierzone",
        "measured_at": acq.now_iso(),
        "pairs": measurements,
        "um_per_px": mean,
        "mm_per_px": mean / 1000.0,
        "px_per_mm": 1000.0 / mean,
        "um_per_px_sd": float(values.std(ddof=1)) if len(values) > 1 else None,
        "spread_rel": spread,
    })
    acq.write_json(directory / "calib.json", record)
    acq.write_checksums(directory)
    acq.journal(study_dir, "calibration_measured",
                {"kind": "scale", "calib_id": calib_id, "um_per_px": mean})

    print(f"Pary ({len(measurements)}):")
    for item in measurements:
        print(f"  {item['p1']} → {item['p2']}   {item['distance_px']:8.2f} px = "
              f"{item['distance_mm']:g} mm   {item['um_per_px']:.3f} µm/px   "
              f"kąt {item['angle_deg']:+.2f}°")
    print(f"\n  µm/px  {mean:.3f}"
          + (f" ± {values.std(ddof=1):.3f}" if len(values) > 1 else ""))
    print(f"  px/mm  {1000.0 / mean:.4f}")
    if len(values) > 1:
        print(f"  rozrzut {spread * 100:.2f} %")
        if spread > SPREAD_WARN:
            print("  UWAGA: rozrzut powyżej 0,5 % — albo wskazania są niedokładne,")
            print("  albo płaszczyzna materiału nie jest prostopadła do osi optycznej.")
    else:
        print("  Jedna para — błąd wskazania pozostaje nieznany. Podaj kilka par.")
    print(f"\n  dotąd zakładane: 35,900 µm/px  →  różnica "
          f"{(mean - 35.9) / 35.9 * 100:+.2f} %")
    common.print_profile_patch("scale_id", calib_id)
    print("  (pole calibration.scale_id; wartość µm/px czytana z calib.json)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-c", "--config", required=True, type=Path)
    parser.add_argument("--shoot", action="store_true",
                        help="zdjęcie wzorca + podgląd z siatką")
    parser.add_argument("--calib", help="identyfikator ujęcia z --shoot")
    parser.add_argument("--pair", action="append", default=[],
                        help="x1,y1,x2,y2,odległość_mm — podawaj wielokrotnie")
    args = parser.parse_args(argv)

    try:
        station, profile, profile_sha, tuning_sha, study_dir = common.setup(args.config)
        if args.shoot:
            return shoot(station, profile, profile_sha, tuning_sha, study_dir)
        if not args.calib or not args.pair:
            raise common.AcquisitionError(
                "Podaj --shoot albo --calib <id> razem z co najmniej jednym --pair.")
        return measure(study_dir, profile, args.calib, args.pair)

    except common.AcquisitionError as exc:
        sys.stdout.flush()
        print(f"\nBŁĄD: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nPrzerwano.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
