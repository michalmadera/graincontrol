"""Zdjęcia silnikiem z acquisition/, żeby nie powstała druga implementacja kontraktu akwizycji."""
from __future__ import annotations

import dataclasses
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

_ACQUISITION = Path(__file__).resolve().parents[2] / "acquisition"
if str(_ACQUISITION) not in sys.path:
    sys.path.insert(0, str(_ACQUISITION))

from server.camera import CameraBusy, CameraManager, make_backend  # noqa: E402
from server.capture import CaptureController  # noqa: E402
from server.config import load_config  # noqa: E402


log = logging.getLogger(__name__)


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
        # Podgląd i zdjęcie korzystają z jednego urządzenia, więc dzielą menedżera z acquisition/.
        self.menedzer = CameraManager(make_backend(konfiguracja))
        self._blad: str | None = None

    def wymus_blad(self, tresc: str) -> None:
        """Tylko do testów: następne ujęcie kończy się błędem."""
        self._blad = tresc

    def resetuj_odniesienie(self) -> None:
        self.kontroler.reference = {"reference_ccm": None, "reference_lux": None}

    @property
    def atrapa(self) -> bool:
        return self.kontroler.config.dummy

    async def zrob(self, numer: int) -> Zdjecie:
        if self._blad:
            tresc, self._blad = self._blad, None
            raise BladZdjecia(tresc)
        try:
            if self.kontroler.session_dir is None:
                # Odniesienie macierzy CCM: pierwsze ujęcie od startu aplikacji (Projekt §8).
                self.kontroler.start_session()
            self.kontroler.set_label(f"probka_{numer}")
            wynik = await self.menedzer.run_exclusive(lambda: self.kontroler.shoot())
        except (CameraBusy, RuntimeError, OSError) as exc:
            log.error("Zdjęcie: %s", exc)
            raise BladZdjecia("Kamera nie zrobiła zdjęcia. Ponów, a jeśli się powtórzy, wezwij serwis.") from exc
        if not wynik["accepted"]:
            log.error("Zdjęcie niezgodne z profilem: %s", wynik["violations"])
            raise BladZdjecia("Zdjęcie niezgodne z ustawieniami kamery. Ponów, a jeśli się powtórzy, wezwij serwis.")
        katalog = self.kontroler.session_dir / wynik["label"]
        stem = wynik["capture_id"]
        dng = katalog / f"{stem}.dng"
        return Zdjecie(katalog / f"{stem}.png", dng if dng.exists() else None,
                       katalog / f"{stem}_meta.json")
