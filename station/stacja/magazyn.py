"""Trwały stan stacji. Musi przeżyć restart i zanik prądu, więc zapis jest atomowy."""
from __future__ import annotations

import json
import os
from pathlib import Path

USTAWIENIA_DOMYSLNE = {
    "skanowanie_wlaczone": False,
    "czas_splywu_s": 30,
    "szczelina_mm": None,       # None: PRZYGOTUJ bez parametru (wartość z printer.cfg)
    "limit_kolejki": 50,
    "oproznianie_co_n": 1,
    "id_stacji": "stacja-1",
}


class Magazyn:
    def __init__(self, katalog: Path) -> None:
        self.katalog = Path(katalog)
        self.katalog.mkdir(parents=True, exist_ok=True)
        self._plik = self.katalog / "stan.json"
        self._dane = self._wczytaj()

    def _wczytaj(self) -> dict:
        try:
            return json.loads(self._plik.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"nastepny_numer": 1, "ustawienia": {}}

    def zapisz(self) -> None:
        tymczasowy = self._plik.with_name(self._plik.name + ".tmp")
        with open(tymczasowy, "w", encoding="utf-8") as plik:
            json.dump(self._dane, plik, ensure_ascii=False, indent=1)
            plik.flush()
            os.fsync(plik.fileno())
        os.replace(tymczasowy, self._plik)

    # ------------------------------------------------------------- numeracja
    def nastepny_numer(self) -> int:
        return self._dane["nastepny_numer"]

    def pobierz_numer(self) -> int:
        """Numer zużywa się przy pobraniu, więc anulowana próbka nie zwalnia go ponownie."""
        numer = self._dane["nastepny_numer"]
        self._dane["nastepny_numer"] = numer + 1
        self.zapisz()
        return numer

    # ------------------------------------------------------------- ustawienia
    @property
    def ustawienia(self) -> dict:
        return {**USTAWIENIA_DOMYSLNE, **self._dane["ustawienia"]}

    def zmien_ustawienia(self, zmiany: dict) -> None:
        nieznane = set(zmiany) - set(USTAWIENIA_DOMYSLNE)
        if nieznane:
            raise ValueError(f"Nieznane ustawienia: {sorted(nieznane)}")
        self._dane["ustawienia"].update(zmiany)
        self.zapisz()
