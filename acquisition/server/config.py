"""Konfiguracja narzędzia akwizycji.

Profil (czas, wzmocnienia, AWB, plik strojenia, ISP) jest wczytywany i **sprawdzany**
tym samym kodem co w CLI: komplet wymaganych pól plus suma kontrolna pliku strojenia.
Plik strojenia bywa podmieniany pod tą samą nazwą przy aktualizacji libcamera i jest to
zmiana, która unieważnia porównywalność bez żadnego widocznego sygnału (§3).

Błąd profilu **nie ubija serwera** — UI ma się podnieść i pokazać przyczynę stałym
paskiem stanu, a przycisk zdjęcia ma być zablokowany (§12.12). Serwer, który nie
wstaje, nie mówi operatorowi nic.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import engine

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = REPO / "profiles" / "acquisition" / "P2-scientific-20260813.json"
DEFAULT_DANE = REPO / "dane"


@dataclass(frozen=True)
class Config:
    profile: dict
    profile_path: Path
    profile_sha256: str | None
    tuning_sha256: str | None
    data_root: Path
    rpicam_still: str
    rpicam_vid: str
    dummy: bool
    blocking_error: str | None

    @property
    def profile_id(self) -> str | None:
        return self.profile.get("profile_id") if self.profile else None


def load_config() -> Config:
    profile_path = Path(os.environ.get("GRAINCONTROL_PROFILE", DEFAULT_PROFILE)).expanduser()
    data_root = Path(os.environ.get("GRAINCONTROL_DANE", DEFAULT_DANE)).expanduser()
    rpicam_still = os.environ.get("GRAINCONTROL_RPICAM_STILL", "rpicam-still")
    rpicam_vid = os.environ.get("GRAINCONTROL_RPICAM_VID", "rpicam-vid")
    dummy = (os.environ.get("GRAINCONTROL_DUMMY", "") == "1"
             or shutil.which(rpicam_still) is None)

    profile, profile_sha, tuning_sha, error = {}, None, None, None
    try:
        profile, profile_sha = engine.load_profile(profile_path)
        # Bez kamery (maszyna deweloperska) pliku strojenia nie ma i nie ma czego
        # sprawdzać; zapis i tak jest wtedy oznaczony jako pochodzący z atrapy.
        if not dummy:
            tuning_sha = engine.verify_tuning_file(profile)
    except engine.AcquisitionError as exc:
        error = str(exc)
    except (OSError, ValueError) as exc:
        error = f"Nie da się wczytać profilu {profile_path}: {exc}"

    return Config(
        profile=profile,
        profile_path=profile_path,
        profile_sha256=profile_sha,
        tuning_sha256=tuning_sha,
        data_root=data_root,
        rpicam_still=rpicam_still,
        rpicam_vid=rpicam_vid,
        dummy=dummy,
        blocking_error=error,
    )
