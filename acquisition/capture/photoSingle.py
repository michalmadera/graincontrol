#!/usr/bin/env python3
"""Jedno zdjęcie z Raspberry Pi HQ Camera — CAŁA automatyka zablokowana.

Ręczna ekspozycja + AWB off + ISP off + scientific tuning (wg rekomendacja.md).
Ustaw stałe niżej pod swoją scenę.

Domyślnie zapisuje PNG. Flaga --both zapisze dodatkowo DNG (RAW 12-bit) obok PNG.
"""
import argparse
from pathlib import Path
from datetime import datetime
import subprocess
import json

WIDTH = 4056
HEIGHT = 3040

OUTPUT_DIR_NAME = "zdjecia/pojedyncze/"

# --- ręczne, stałe (auto zablokowane) ---
EXPOSURE = 65000          # czas naświetlania [us] (stały -> AEC off)
ANALOGUE_GAIN = 1.0       # gain 1.0 (AGC off, najmniej szumu)
RED_GAIN = 2.36           # ręczny balans bieli: czerwień
BLUE_GAIN = 2.19          # ręczny balans bieli: niebieski
SAVE_RAW = False          # True -> dodatkowo DNG 12-bit

TUNING_CANDIDATES = [
    "/usr/share/libcamera/ipa/rpi/pisp/imx477_scientific.json",  # Pi 5
    "/usr/share/libcamera/ipa/rpi/vc4/imx477_scientific.json",   # Pi 4
]


def find_tuning_file():
    for p in TUNING_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def take_photo(output_path: Path, metadata_path: Path, save_raw=SAVE_RAW):
    tuning = find_tuning_file()
    command = [
        "rpicam-still",
        "-o", str(output_path),
        "--encoding", "png",
        "--width", str(WIDTH), "--height", str(HEIGHT),

        # ręczna ekspozycja -> AEC/AGC off
        "--shutter", str(EXPOSURE),
        "--gain", str(ANALOGUE_GAIN),

        # ręczny balans bieli -> AWB off
        "--awb", "off",
        "--awbgains", f"{RED_GAIN},{BLUE_GAIN}",

        # ISP off (bez wyostrzania/denoise/koloryzacji)
        "--sharpness", "0", "--denoise", "off",
        "--contrast", "1.0", "--saturation", "1.0", "--brightness", "0",

        # bez okresu preview -> deterministycznie (i tak nic nie ma się "auto" dostroić)
        "--immediate",

        "--metadata", str(metadata_path), "--metadata-format", "json",
    ]
    if tuning:
        command += ["--tuning-file", tuning]
    else:
        print("UWAGA: brak imx477_scientific.json — obraz 'upiększony' przez ISP.")
    if save_raw:
        command.append("--raw")   # DNG (RAW 12-bit) zapisany obok PNG

    fmt = "PNG + DNG" if save_raw else "PNG"
    print(f"Wykonywanie zdjęcia ({fmt}, cała automatyka zablokowana)...")
    subprocess.run(command, check=True)


def load_metadata(metadata_path: Path) -> dict:
    try:
        with metadata_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser(description="Jedno zdjęcie Pi HQ Camera (auto zablokowane)")
    ap.add_argument("--both", action="store_true",
                    help="zapisz DNG (RAW 12-bit) obok PNG")
    args = ap.parse_args()
    save_raw = args.both or SAVE_RAW

    print("=== Pi HQ Camera — jedno zdjęcie (auto zablokowane) ===")
    print("Ostrość i przysłonę ustawiasz ręcznie na obiektywie.\n")
    try:
        output_dir = Path.home() / OUTPUT_DIR_NAME
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = output_dir / f"hq_capture_{timestamp}.png"
        metadata_path = output_dir / f"hq_capture_{timestamp}_metadata.json"

        take_photo(image_path, metadata_path, save_raw=save_raw)
        m = load_metadata(metadata_path)

        print(f"\nZdjęcie: {image_path}")
        if save_raw:
            print(f"RAW DNG: {image_path.with_suffix('.dng')}")
        print(f"Metadane: {metadata_path}\n")
        print("Parametry ujęcia (z metadanych — powinny być stałe między zdjęciami):")
        print(f"  ExposureTime: {m.get('ExposureTime')} us")
        print(f"  AnalogueGain: {m.get('AnalogueGain')}")
        print(f"  DigitalGain:  {m.get('DigitalGain')}")
        print(f"  ColourGains:  {m.get('ColourGains')}")
        print(f"  Lux:          {m.get('Lux')}")

    except subprocess.CalledProcessError as e:
        print(f"Błąd rpicam-still (kod {e.returncode}).")
    except FileNotFoundError:
        print("Nie znaleziono 'rpicam-still' — zainstaluj rpicam-apps.")
    except KeyboardInterrupt:
        print("\nPrzerwano.")
    except Exception as e:
        print(f"Nieoczekiwany błąd: {e}")

    input("Naciśnij Enter, aby zamknąć skrypt...")


if __name__ == "__main__":
    main()
