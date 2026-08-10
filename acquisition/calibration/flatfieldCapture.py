#!/usr/bin/env python3
"""Korekcja winietowania — flat-field z serii ujęć jednorodnej bieli (§7, §12.7).

Obowiązkowa po przejściu na `imx477_scientific.json`: ten plik strojenia **nie zawiera
bloku ALSC**, więc korekcji winietowania nie ma w torze wcale. Dotychczasowa płaskość
pola (rozpiętość P98 L* = 3,3 jedn.) była po części zasługą ALSC z pliku domyślnego
(rekomendacja §3 i errata).

Seria ≥ 10 ujęć jest uśredniana, żeby szum sensora nie wszedł do mapy korekcji. Mapa
powstaje z obrazu **pomniejszonego** i jest zapisywana w tej postaci: winietowanie jest
gładkie, a pełnorozdzielczościowa mapa 12 Mpx przechowywałaby głównie szum. Skuteczność
korekcji mierzy `illum_range_p98_L` przed i po — i jest liczona po zastosowaniu mapy
pomniejszonej z powrotem na pełnym kadrze, więc obejmuje też stratę na wygładzeniu.

    flatfieldCapture.py -c station.json --frames 10
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import calibCommon as common
from calibCommon import acq, stats

MIN_MEAN_DN = 60


def block_mean(image: np.ndarray, factor: int) -> np.ndarray:
    """Pomniejszenie przez uśrednienie bloków factor×factor (bez interpolacji)."""
    height = image.shape[0] // factor * factor
    width = image.shape[1] // factor * factor
    trimmed = image[:height, :width]
    return trimmed.reshape(height // factor, factor,
                           width // factor, factor, -1).mean(axis=(1, 3))


def upsample(small: np.ndarray, shape) -> np.ndarray:
    """Powrót do pełnej rozdzielczości, dwuliniowo, kanał po kanale."""
    height, width = shape
    channels = []
    for index in range(small.shape[2]):
        layer = Image.fromarray(small[..., index].astype(np.float32), mode="F")
        channels.append(np.asarray(layer.resize((width, height), Image.BILINEAR)))
    return np.stack(channels, axis=-1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-c", "--config", required=True, type=Path)
    parser.add_argument("--frames", type=int, default=10,
                        help="liczba ujęć do uśrednienia (min. 10 wg §7)")
    parser.add_argument("--downsample", type=int, default=8,
                        help="krotność pomniejszenia mapy korekcji")
    args = parser.parse_args(argv)

    try:
        if args.frames < 2:
            raise common.AcquisitionError("--frames musi być >= 2")
        station, profile, profile_sha, tuning_sha, study_dir = common.setup(args.config)
        calib_id, directory = common.new_calib_dir(study_dir, "flatfield")
        print("Wypełnij cały kadr jednorodną białą powierzchnią, bez cieni i pyłu.")
        print(f"Seria {args.frames} ujęć na parametrach profilu {profile['profile_id']}\n")

        reference = {"reference_ccm": None, "reference_lux": None}
        accumulator = None
        frames = []
        for index in range(args.frames):
            image, meta, command = common.capture_into(
                station, profile, directory, f"frame_{index + 1:02d}")
            violations = common.contract_violations(meta, profile, reference)
            if violations:
                raise common.AcquisitionError(
                    "Ujęcie kalibracyjne narusza kontrakt: " + "; ".join(violations)
                    + "\n  Mapa korekcji zrobiona na innych parametrach niż materiał\n"
                      "  nie opisuje tego samego toru.")
            rgb = stats.load_rgb(image)
            frame = stats.frame_stats(rgb)
            frames.append({"frame": index + 1, "stats": frame,
                           "lux": meta.get("Lux"), "command_line": command})
            print(f"  ujęcie {index + 1:2d}/{args.frames}   max {frame['max_dn']:3d} DN   "
                  f"średnia {frame['mean_dn']:6.1f} DN   klip {frame['clip_frac'] * 100:.3f}%")
            if frame["clip_frac"] > 0:
                raise common.AcquisitionError(
                    "Biała powierzchnia przestrzeliwuje przy parametrach profilu.\n"
                    "  Flat-field musi powstać na tym samym czasie co materiał, więc\n"
                    "  zmniejsz jasność powierzchni, a nie czas naświetlania.")
            accumulator = (rgb.astype(np.float32) if accumulator is None
                           else accumulator + rgb)
            del rgb

        mean_image = accumulator / args.frames
        del accumulator
        if mean_image.mean() < MIN_MEAN_DN:
            raise common.AcquisitionError(
                f"Średni poziom {mean_image.mean():.1f} DN jest za niski — mapa korekcji "
                "opisywałaby głównie szum.")

        small = block_mean(mean_image, args.downsample)
        centre = small[small.shape[0] // 5 * 2:small.shape[0] // 5 * 3,
                       small.shape[1] // 5 * 2:small.shape[1] // 5 * 3]
        target = np.median(centre.reshape(-1, 3), axis=0)
        gain_small = (target / np.maximum(small, 1.0)).astype(np.float32)

        before = stats.illumination_range(stats.lightness_full(
            np.clip(mean_image, 0, 255).astype(np.uint8)))
        corrected = np.clip(mean_image * upsample(gain_small, mean_image.shape[:2]),
                            0, 255).astype(np.uint8)
        after = stats.illumination_range(stats.lightness_full(corrected))

        Image.fromarray(corrected[::4, ::4]).save(directory / "corrected_preview.png")
        del corrected
        Image.fromarray(np.clip(mean_image, 0, 255).astype(np.uint8)[::4, ::4]).save(
            directory / "mean_preview.png")
        np.savez_compressed(directory / "flatfield.npz", gain=gain_small)

        common.finish(study_dir, "flatfield", calib_id, directory, {
            "profile_id": profile["profile_id"],
            "profile_sha256": profile_sha,
            "tuning_file_sha256": tuning_sha,
            "frames": frames,
            "downsample": args.downsample,
            "upsample": "PIL bilinear na mapie wzmocnień, kanał po kanale",
            "target_rgb": target.tolist(),
            "gain_min": float(gain_small.min()), "gain_max": float(gain_small.max()),
            "illum_range_p98_L_before": before,
            "illum_range_p98_L_after": after,
        })

        print(f"\nZapisano {directory}")
        print(f"  wzmocnienia w mapie:      {gain_small.min():.3f} – {gain_small.max():.3f}")
        print(f"  rozpiętość P98 L* przed:  {before['range_L']:.2f} jedn.")
        print(f"  rozpiętość P98 L* po:     {after['range_L']:.2f} jedn.")
        if after["range_L"] >= before["range_L"]:
            print("  UWAGA: korekcja nie poprawiła równomierności — sprawdź, czy "
                  "powierzchnia była jednorodna i czy nie było cieni.")
        common.print_profile_patch("flatfield_id", calib_id)
        print('  (pole calibration.flatfield_id)')
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
