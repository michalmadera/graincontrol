"""Konfiguracja prostego narzędzia akwizycji.

Cel jest wąski: zrobić serię zdjęć na **zamrożonych parametrach** i zapisać je do
`dane/sesja_.../NAZWA/`. Potrzebujemy więc tylko profilu (parametry kamery: czas,
wzmocnienia, AWB, plik strojenia, ISP) oraz katalogu na dane. Żadnego kontraktu,
manifestu ani QC — to była maszyneria toru badawczego, nie tego narzędzia.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = REPO / "profiles" / "acquisition" / "P1-scientific-20260810.json"
DEFAULT_DANE = REPO / "dane"


@dataclass(frozen=True)
class Config:
    profile: dict
    profile_path: Path
    data_root: Path
    rpicam_still: str
    rpicam_vid: str
    force_dummy: bool


def load_config() -> Config:
    profile_path = Path(os.environ.get("GRAINCONTROL_PROFILE", DEFAULT_PROFILE)).expanduser()
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    data_root = Path(os.environ.get("GRAINCONTROL_DANE", DEFAULT_DANE)).expanduser()
    return Config(
        profile=profile,
        profile_path=profile_path,
        data_root=data_root,
        rpicam_still=os.environ.get("GRAINCONTROL_RPICAM_STILL", "rpicam-still"),
        rpicam_vid=os.environ.get("GRAINCONTROL_RPICAM_VID", "rpicam-vid"),
        # bez rpicam w systemie (dev) używamy atrapy — patrz capture.py / camera.py
        force_dummy=os.environ.get("GRAINCONTROL_DUMMY", "") == "1",
    )
