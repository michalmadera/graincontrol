"""Raport o GPU do /health: brak karty to informacja, nie awaria."""
from __future__ import annotations

import shutil
import subprocess


def raport_gpu() -> dict:
    try:
        import torch
    except ImportError:
        torch = None
    if torch is not None and torch.cuda.is_available():
        return {"dostepne": True, "nazwa": torch.cuda.get_device_name(0), "zrodlo": "torch"}
    if torch is None and shutil.which("nvidia-smi"):
        wynik = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10, check=False)
        if wynik.returncode == 0 and wynik.stdout.strip():
            return {"dostepne": True, "nazwa": wynik.stdout.strip().splitlines()[0],
                    "zrodlo": "nvidia-smi"}
    return {"dostepne": False, "nazwa": None, "zrodlo": "torch" if torch else None}
