"""Zdjęcia silnikiem z acquisition/, żeby nie powstała druga implementacja kontraktu akwizycji."""
from __future__ import annotations

import dataclasses
import sys
from dataclasses import dataclass
from pathlib import Path

_ACQUISITION = Path(__file__).resolve().parents[2] / "acquisition"
if str(_ACQUISITION) not in sys.path:
    sys.path.insert(0, str(_ACQUISITION))

from server.capture import CaptureController  # noqa: E402
from server.config import load_config  # noqa: E402


class BladZdjecia(RuntimeError):
    """Zdjęcia nie ma albo jest niezgodne z profilem. Maszyna jest sprawna, wolno ponowić."""


@dataclass(frozen=True)
class Zdjecie:
    png: Path
    dng: Path | None
    meta: Path


class Kamera:
    def __init__(self, katalog: Path) -> None:
        konfiguracja = dataclasses.replace(load_config(), data_root=Path(katalog) / "zdjecia")
        self.kontroler = CaptureController(konfiguracja)
        self._blad: str | None = None

    def wymus_blad(self, tresc: str) -> None:
        """Tylko do testów: następne ujęcie kończy się błędem."""
        self._blad = tresc

    async def zrob(self, numer: int) -> Zdjecie:
        if self._blad:
            tresc, self._blad = self._blad, None
            raise BladZdjecia(tresc)
        try:
            if self.kontroler.session_dir is None:
                # Odniesienie macierzy CCM: pierwsze ujęcie od startu aplikacji (Projekt §8).
                self.kontroler.start_session()
            self.kontroler.set_label(f"probka_{numer}")
            wynik = await self.kontroler.shoot()
        except RuntimeError as exc:
            raise BladZdjecia(str(exc)) from exc
        if not wynik["accepted"]:
            raise BladZdjecia("; ".join(wynik["violations"]) or "Zdjęcie niezgodne z profilem")
        katalog = self.kontroler.session_dir / wynik["label"]
        stem = wynik["capture_id"]
        dng = katalog / f"{stem}.dng"
        return Zdjecie(katalog / f"{stem}.png", dng if dng.exists() else None,
                       katalog / f"{stem}_meta.json")
