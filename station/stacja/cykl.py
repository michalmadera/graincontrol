"""Automat cyklu: jedyne miejsce, które decyduje, który ekran widzi robotnik."""
from __future__ import annotations

import asyncio
import time

from .magazyn import Magazyn
from .maszyna import BladMakra, BrakPolaczenia, Maszyna


class Cykl:
    def __init__(self, maszyna: Maszyna, magazyn: Magazyn, tempo: float = 1.0) -> None:
        self.maszyna = maszyna
        self.magazyn = magazyn
        self.tempo = tempo
        self.krok = "gotowa"
        self.numer_probki: int | None = None
        self._koniec_splywu: float | None = None
        self._zadanie: asyncio.Task | None = None

    @property
    def trwa(self) -> bool:
        return self._zadanie is not None and not self._zadanie.done()

    def _ekran(self) -> str:
        stan = self.maszyna.stan()
        if not stan.polaczona or stan.webhooks != "ready":
            return "brak_polaczenia"
        if self.trwa:
            return self.krok
        # Kalibracja wynika ze stanu maszyny, nie z pamięci aplikacji: restart Klippera kasuje
        # skalibrowany, więc tej ścieżki nie da się ominąć.
        if not stan.skalibrowany:
            return "kalibracja"
        return self.krok

    def opis(self) -> dict:
        pozostalo = None
        if self._koniec_splywu is not None:
            pozostalo = max(0, round((self._koniec_splywu - time.monotonic()) / self.tempo))
        return {
            "ekran": self._ekran(),
            "trwa": self.trwa,
            "numer_probki": self.numer_probki,
            "nastepny_numer": self.magazyn.nastepny_numer(),
            "pozostalo_s": pozostalo,
        }

    def akcja(self, nazwa: str) -> None:
        obsluga = {
            "kalibruj": self._kalibruj,
            "nowy_pomiar": self._nowy_pomiar,
            "probka_wsypana": self._probka_wsypana,
            "anuluj": self._anuluj,
        }.get(nazwa)
        if obsluga is None:
            raise ValueError(f"Nieznana akcja: {nazwa}")
        if self.trwa:
            raise ValueError("Maszyna pracuje")
        obsluga()

    def _wymagaj(self, ekran: str) -> None:
        if self._ekran() != ekran:
            raise ValueError(f"Akcja niedostępna na ekranie {self._ekran()}")

    def _uruchom(self, koro) -> None:
        self._zadanie = asyncio.create_task(koro)

    # ------------------------------------------------------------- kalibracja
    def _kalibruj(self) -> None:
        self._wymagaj("kalibracja")
        self.krok = "kalibracja"
        self._uruchom(self._po_kalibracji())

    async def _po_kalibracji(self) -> None:
        try:
            await self.maszyna.wywolaj("KALIBRUJ")
        except (BladMakra, BrakPolaczenia):
            return
        self.krok = "gotowa"

    # ------------------------------------------------------------- pomiar
    def _nowy_pomiar(self) -> None:
        self._wymagaj("gotowa")
        self.numer_probki = self.magazyn.pobierz_numer()
        self.krok = "przygotowanie"
        self._uruchom(self._przygotuj())

    async def _przygotuj(self) -> None:
        szczelina = self.magazyn.ustawienia["szczelina_mm"]
        makro = "PRZYGOTUJ" if szczelina is None else f"PRZYGOTUJ SZCZELINA={szczelina}"
        try:
            await self.maszyna.wywolaj(makro)
        except (BladMakra, BrakPolaczenia):
            return
        self.krok = "wsyp"

    def _probka_wsypana(self) -> None:
        self._wymagaj("wsyp")
        self.krok = "splyw"
        self._uruchom(self._splyw_i_rozgarnianie())

    async def _splyw_i_rozgarnianie(self) -> None:
        czas = self.magazyn.ustawienia["czas_splywu_s"] * self.tempo
        self._koniec_splywu = time.monotonic() + czas
        await asyncio.sleep(czas)
        self._koniec_splywu = None
        self.krok = "rozgarnianie"
        try:
            await self.maszyna.wywolaj("POMIAR")
        except (BladMakra, BrakPolaczenia):
            return
        self.krok = "zdjecie"

    def _anuluj(self) -> None:
        self._wymagaj("wsyp")
        self.numer_probki = None
        # Robotnik nacisnął „Anuluj”, a nie kalibrację: maszyna rusza dopiero po drugim przycisku.
        self.krok = "kalibracja"
