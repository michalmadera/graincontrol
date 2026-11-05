"""Automat cyklu: jedyne miejsce, które decyduje, który ekran widzi robotnik."""
from __future__ import annotations

import asyncio

from .maszyna import BladMakra, BrakPolaczenia, Maszyna


class Cykl:
    def __init__(self, maszyna: Maszyna) -> None:
        self.maszyna = maszyna
        self.krok = "gotowa"
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
        return {"ekran": self._ekran(), "trwa": self.trwa}

    def akcja(self, nazwa: str) -> None:
        obsluga = {"kalibruj": self._kalibruj}.get(nazwa)
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
