#!/usr/bin/env python3
"""Augmentacja koloru: seria zdjęć tej samej sceny ze zmiennym balansem bieli (Red/Blue gain).

Ten sam kadr, różne odcienie -> darmowa augmentacja koloru do treningu (jedna maska
pasuje do wszystkich wariantów). CAŁA automatyka kamery zablokowana (wg rekomendacja.md):
ręczna ekspozycja + AWB off + ISP off + scientific tuning.

Zmień listy RED_GAINS / BLUE_GAINS — robi zdjęcie dla KAŻDEJ kombinacji (grid).
"""
from pathlib import Path
from datetime import datetime
import subprocess

WIDTH = 4056
HEIGHT = 3040

OUTPUT_DIR_NAME = "zdjecia/augment/"

# --- stałe (ręczne, niezmienne) ---
EXPOSURE = 65000          # czas naświetlania [us] (stały -> AEC off)
ANALOGUE_GAIN = 1.0       # gain 1.0 (AGC off, najmniej szumu)
SAVE_RAW = False

# --- WARIANTY KOLORU: pary (Red_gain, Blue_gain) od CIEPŁEGO do ZIMNEGO ---
# Wyższy R / niższy B = cieplej; niższy R / wyższy B = zimniej. Środek = neutralny.
# 5 wariantów wzdłuż osi warm->cool to sensowna augmentacja koloru na scenę
# (więcej nie ma sensu — energię włóż w RÓŻNE sceny, nie kolory tej samej).
GAIN_PAIRS = [
    (2.70, 1.95),   # ciepły
    (2.52, 2.07),   # lekko ciepły
    (2.36, 2.19),   # neutralny (baza)
    (2.18, 2.38),   # lekko zimny
    (2.00, 2.58),   # zimny
]

TUNING_CANDIDATES = [
    "/usr/share/libcamera/ipa/rpi/pisp/imx477_scientific.json",  # Pi 5
    "/usr/share/libcamera/ipa/rpi/vc4/imx477_scientific.json",   # Pi 4
]


def find_tuning_file():
    for p in TUNING_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def take_photo(red_gain, blue_gain, output_path, metadata_path, tuning):
    command = [
        "rpicam-still",
        "-o", str(output_path),
        "--encoding", "png",
        "--width", str(WIDTH), "--height", str(HEIGHT),

        # ręczna ekspozycja -> AEC/AGC off
        "--shutter", str(EXPOSURE),
        "--gain", str(ANALOGUE_GAIN),

        # ręczny balans bieli -> AWB off (to jest to, co sweepujemy)
        "--awb", "off",
        "--awbgains", f"{red_gain},{blue_gain}",

        # ISP off (bez upiększania)
        "--sharpness", "0", "--denoise", "off",
        "--contrast", "1.0", "--saturation", "1.0", "--brightness", "0",

        "--immediate",
        "--metadata", str(metadata_path), "--metadata-format", "json",
    ]
    if tuning:
        command += ["--tuning-file", tuning]
    if SAVE_RAW:
        command.append("--raw")
    subprocess.run(command, check=True)


def main():
    print("=== Augmentacja koloru (warianty Red/Blue gain) ===")
    print("Ostrość i przysłonę ustawiasz ręcznie na obiektywie.")
    total = len(GAIN_PAIRS)
    print(f"Zrobię {total} zdjęć (warianty koloru od ciepłego do zimnego) TEJ SAMEJ sceny.\n")

    output_dir = Path.home() / OUTPUT_DIR_NAME
    output_dir.mkdir(parents=True, exist_ok=True)
    tuning = find_tuning_file()
    if not tuning:
        print("UWAGA: brak imx477_scientific.json — obraz 'upiększony' przez ISP.")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        for i, (r, b) in enumerate(GAIN_PAIRS, 1):
            base = f"hq_{stamp}_{i:02d}_R{r}_B{b}"
            img = output_dir / f"{base}.png"
            meta = output_dir / f"{base}_metadata.json"
            print(f"[{i}/{total}] R={r} B={b} -> {img.name}")
            take_photo(r, b, img, meta, tuning)
        print(f"\nGotowe — {total} zdjęć w: {output_dir}")
        print("Ten sam kadr, różne odcienie — JEDNA maska pasuje do wszystkich (policz raz, reużyj).")

    except subprocess.CalledProcessError as e:
        print(f"Błąd rpicam-still (kod {e.returncode}).")
    except FileNotFoundError:
        print("Nie znaleziono 'rpicam-still' — zainstaluj rpicam-apps.")
    except KeyboardInterrupt:
        print("\nPrzerwano.")

    input("Naciśnij Enter, aby zamknąć...")


if __name__ == "__main__":
    main()
