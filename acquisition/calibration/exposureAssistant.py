#!/usr/bin/env python3
"""Dobór czasu naświetlania — drabinka ujęć próbnych (spec-akwizycji.md §12.6).

Po przejściu na `imx477_scientific.json` czas trzeba dobrać od nowa: ten plik ma
łagodniejszą krzywą tonalną (Rec.709 zamiast domyślnej) i wyłączone wzmocnienie
kontrastu, więc obraz przy tym samym czasie jest ciemniejszy (rekomendacja §3).

Odniesieniem jest **wzorzec bieli w kadrze**, nie najjaśniejszy kamyk (rekomendacja §4).
Bez wzorca skala L* nie jest do niczego zakotwiczona, a jasność najjaśniejszego ziarna
opisuje ekspozycję, nie materiał. Wzorzec ma sięgać 220–230 DN — czyli 85–90% zakresu,
z zapasem na ziarna jaśniejsze od typowych i bez ryzyka przesterowania.

Ujęcia próbne trafiają do `calib/exposure_<id>/`, nigdy do zbioru pomiarowego.

    exposureAssistant.py -c station.json --from 40000 --to 110000 --steps 8
    exposureAssistant.py -c station.json --shutters 60000,65000,70000,75000
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import calibCommon as common
from calibCommon import acq, stats


def ladder(args) -> list[int]:
    if args.shutters:
        return sorted(int(v) for v in args.shutters.split(","))
    if args.steps < 2:
        raise common.AcquisitionError("--steps musi być >= 2")
    span = (args.to_us - args.from_us) / (args.steps - 1)
    return [int(round(args.from_us + span * i)) for i in range(args.steps)]


def white_patch_roi(profile: dict, name: str) -> list[int]:
    for patch in profile.get("reference_patches") or []:
        if patch.get("name") == name:
            return patch["roi"]
    raise common.AcquisitionError(
        f"Profil nie ma wzorca '{name}' w reference_patches.\n"
        "  Bez wzorca w kadrze dobór czasu nie ma odniesienia (rekomendacja §4).")


def propose(rows: list[dict], low: int, high: int) -> dict:
    """Największy czas, przy którym wzorzec mieści się w oknie i nic nie przestrzeliwuje."""
    clean = [r for r in rows if r["frame"]["clip_frac"] == 0.0
             and r["patch"]["clip_frac"] == 0.0]
    inside = [r for r in clean if low <= r["patch"]["p99_dn"] <= high]
    if inside:
        best = max(inside, key=lambda r: r["shutter_us"])
        return {"shutter_us": best["shutter_us"], "basis": "pomiar",
                "patch_p99_dn": best["patch"]["p99_dn"]}

    below = [r for r in clean if r["patch"]["p99_dn"] < low]
    above = [r for r in rows if r["patch"]["p99_dn"] > high]
    if below and above:
        lower = max(below, key=lambda r: r["patch"]["p99_dn"])
        upper = min(above, key=lambda r: r["patch"]["p99_dn"])
        target = (low + high) / 2
        fraction = ((target - lower["patch"]["p99_dn"])
                    / (upper["patch"]["p99_dn"] - lower["patch"]["p99_dn"]))
        interpolated = lower["shutter_us"] + fraction * (upper["shutter_us"]
                                                         - lower["shutter_us"])
        return {"shutter_us": int(round(interpolated / 500) * 500),
                "basis": "interpolacja",
                "between": [lower["shutter_us"], upper["shutter_us"]],
                "warning": "DN nie jest liniowe względem czasu (krzywa tonalna), "
                           "więc interpolację trzeba potwierdzić ujęciem kontrolnym"}
    if below:
        return {"shutter_us": None, "basis": "brak",
                "warning": "cała drabinka poniżej okna — wydłuż czasy"}
    return {"shutter_us": None, "basis": "brak",
            "warning": "cała drabinka przesterowana lub w oknie brak ujęcia bez klipu — "
                       "skróć czasy"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-c", "--config", required=True, type=Path)
    parser.add_argument("--from", dest="from_us", type=int, default=40000,
                        help="początek drabinki [us]")
    parser.add_argument("--to", dest="to_us", type=int, default=110000,
                        help="koniec drabinki [us]")
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--shutters", help="jawna lista czasów po przecinku [us]")
    parser.add_argument("--patch", default="white", help="nazwa wzorca z profilu")
    parser.add_argument("--target-low", type=int, default=220,
                        help="dolna granica okna DN wzorca (rekomendacja §4)")
    parser.add_argument("--target-high", type=int, default=230)
    args = parser.parse_args(argv)

    try:
        station, profile, profile_sha, tuning_sha, study_dir = common.setup(args.config)
        roi = white_patch_roi(profile, args.patch)
        times = ladder(args)
        calib_id, directory = common.new_calib_dir(study_dir, "exposure")
        print(f"Drabinka {len(times)} ujęć: {', '.join(str(t) for t in times)} us")
        print(f"Wzorzec '{args.patch}' ROI {roi}, okno docelowe "
              f"{args.target_low}–{args.target_high} DN\n")

        reference = {"reference_ccm": None, "reference_lux": None}
        rows = []
        for shutter in times:
            image, meta, command = common.capture_into(
                station, profile, directory, f"shutter_{shutter}", shutter_us=shutter)
            violations = common.contract_violations(meta, profile, reference, shutter)
            rgb = stats.load_rgb(image)
            row = {
                "shutter_us": shutter,
                "frame": stats.frame_stats(rgb),
                "patch": stats.patch_stats(rgb, roi),
                "metadata": {k: meta.get(k) for k in
                             ("ExposureTime", "AnalogueGain", "DigitalGain",
                              "ColourGains", "Lux")},
                "contract_violations": violations,
                "command_line": command,
            }
            rows.append(row)
            flag = "  ← kontrakt: " + "; ".join(violations) if violations else ""
            print(f"  {shutter:7d} us   wzorzec L* {row['patch']['L_median']:6.2f}   "
                  f"P99 {row['patch']['p99_dn']:3d} DN   kadr max {row['frame']['max_dn']:3d} DN   "
                  f"klip {row['frame']['clip_frac'] * 100:.3f}%{flag}")

        result = propose(rows, args.target_low, args.target_high)
        common.finish(study_dir, "exposure", calib_id, directory, {
            "profile_id": profile["profile_id"],
            "profile_sha256": profile_sha,
            "tuning_file_sha256": tuning_sha,
            "patch": args.patch, "roi": roi,
            "target_dn": [args.target_low, args.target_high],
            "ladder": rows,
            "proposal": result,
        })

        print(f"\nZapisano {directory}")
        if result["shutter_us"] is None:
            print(f"BRAK PROPOZYCJI: {result['warning']}")
            return 1
        print(f"Propozycja: shutter_us = {result['shutter_us']} ({result['basis']})")
        if "warning" in result:
            print(f"  uwaga: {result['warning']}")
        common.print_profile_patch("shutter_us", result["shutter_us"])
        print("  Zmiana czasu unieważnia porównywalność z materiałem zebranym wcześniej.")
        return 0

    except common.AcquisitionError as exc:
        sys.stdout.flush()
        print(f"\nBŁĄD: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nPrzerwano.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
