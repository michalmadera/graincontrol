"""Kolejka pomiarów na dysku: zdjęcie jest tu zapisane, zanim ktokolwiek spróbuje je wysłać."""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .kamera import Zdjecie


@dataclass(frozen=True)
class Wpis:
    katalog: Path

    @property
    def png(self) -> Path:
        return self.katalog / "zdjecie.png"

    @property
    def dng(self) -> Path | None:
        sciezka = self.katalog / "zdjecie.dng"
        return sciezka if sciezka.exists() else None

    @property
    def pomiar(self) -> dict:
        return json.loads((self.katalog / "pomiar.json").read_text(encoding="utf-8"))


class Kolejka:
    def __init__(self, katalog: Path) -> None:
        self.katalog = Path(katalog) / "kolejka"
        self.katalog.mkdir(parents=True, exist_ok=True)

    def oczekujace(self) -> list[Wpis]:
        """FIFO. Wpis bez pomiar.json to przerwany zapis: nigdy nie został przyjęty do kolejki."""
        return [Wpis(k) for k in sorted(self.katalog.iterdir())
                if k.is_dir() and (k / "pomiar.json").exists()]

    def dodaj(self, zdjecie: Zdjecie, pomiar: dict) -> Wpis:
        kolejny = max((int(k.name.split("_")[0]) for k in self.katalog.iterdir()
                       if k.name.split("_")[0].isdigit()), default=0) + 1
        katalog = self.katalog / f"{kolejny:08d}_{pomiar['id_pomiaru']}"
        katalog.mkdir()
        os.replace(zdjecie.png, katalog / "zdjecie.png")
        if zdjecie.dng:
            os.replace(zdjecie.dng, katalog / "zdjecie.dng")
        akwizycja = json.loads(zdjecie.meta.read_text(encoding="utf-8"))
        tymczasowy = katalog / "pomiar.json.tmp"
        # pomiar.json powstaje ostatni i atomowo: jego obecność znaczy „wpis kompletny”.
        with open(tymczasowy, "w", encoding="utf-8") as plik:
            json.dump({**pomiar, "akwizycja": akwizycja}, plik, ensure_ascii=False)
            plik.flush()
            os.fsync(plik.fileno())
        os.replace(tymczasowy, katalog / "pomiar.json")
        return Wpis(katalog)

    def usun(self, wpis: Wpis) -> None:
        shutil.rmtree(wpis.katalog)

    def odrzuc(self, wpis: Wpis) -> None:
        """Poza kolejką i poza limitem, ale zostaje na dysku do wglądu serwisu."""
        cel = self.katalog.with_name("kolejka_odrzucone")
        cel.mkdir(exist_ok=True)
        os.replace(wpis.katalog, cel / wpis.katalog.name)
