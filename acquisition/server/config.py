"""Wczytanie konfiguracji stanowiska i profilu akwizycji dla serwera UI.

Serwer **nie** przepisuje logiki `captureSample.py` — czyta te same pliki
(`station.json`, profil §3) tylko do wyświetlania i do parametrów QC/podglądu.
Wykonanie ujęcia idzie przez silnik (patrz `capture_engine.py`), a nie stąd.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    station_path: Path
    station: dict
    profile_path: Path
    profile: dict

    @property
    def archive_root(self) -> Path:
        return Path(self.station["archive_root"]).expanduser()

    @property
    def study_id(self) -> str:
        # study_id jest zagnieżdżony w bloku "study" (jak w captureSample)
        return self.station["study"]["study_id"]

    @property
    def study_dir(self) -> Path:
        return self.archive_root / self.study_id

    @property
    def profile_id(self) -> str:
        return self.profile["profile_id"]


def load_config(station_path: str | Path) -> Config:
    """Wczytuje station.json i wskazany przez niego profil.

    `profile_path` w station.json jest względny do pliku stacji — tak samo
    interpretuje go `captureSample.load_station`, więc rozwiązujemy identycznie,
    żeby serwer i silnik widziały ten sam profil.
    """
    station_path = Path(station_path).expanduser().resolve()
    station = json.loads(station_path.read_text(encoding="utf-8"))

    raw_profile = Path(station["profile_path"])
    profile_path = (raw_profile if raw_profile.is_absolute()
                    else (station_path.parent / raw_profile)).resolve()
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    return Config(station_path=station_path, station=station,
                  profile_path=profile_path, profile=profile)
