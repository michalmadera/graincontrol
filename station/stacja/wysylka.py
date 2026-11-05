"""Wysyłka pomiarów na serwer: kolejność FIFO, plik znika dopiero po zapisaniu wyniku."""
from __future__ import annotations

import asyncio
import json

import httpx

from .kolejka import Kolejka, Wpis
from .magazyn import Magazyn

LIMIT_CZASU_S = 60.0


class Wysylka:
    def __init__(self, kolejka: Kolejka, magazyn: Magazyn, adres: str,
                 transport: httpx.AsyncBaseTransport | None = None, tempo: float = 1.0) -> None:
        self.kolejka = kolejka
        self.magazyn = magazyn
        self.adres = adres
        self.tempo = tempo
        self._transport = transport
        self._nowe = asyncio.Event()
        self._zadanie: asyncio.Task | None = None

    def start(self) -> None:
        self._zadanie = asyncio.create_task(self._petla())

    async def stop(self) -> None:
        if self._zadanie:
            self._zadanie.cancel()
            await asyncio.gather(self._zadanie, return_exceptions=True)
            self._zadanie = None

    def obudz(self) -> None:
        self._nowe.set()

    async def _petla(self) -> None:
        async with httpx.AsyncClient(transport=self._transport, timeout=LIMIT_CZASU_S) as klient:
            while True:
                self._nowe.clear()
                wpisy = self.kolejka.oczekujace()
                if not wpisy:
                    await self._nowe.wait()
                    continue
                await self._wyslij(klient, wpisy[0])

    async def _wyslij(self, klient: httpx.AsyncClient, wpis: Wpis) -> None:
        pomiar = wpis.pomiar
        pliki = {"zdjecie": ("zdjecie.png", wpis.png.read_bytes(), "image/png")}
        if wpis.dng:
            pliki["raw"] = ("zdjecie.dng", wpis.dng.read_bytes(), "application/octet-stream")
        odpowiedz = await klient.post(f"{self.adres}/api/v1/pomiary", files=pliki,
                                      data={"metadane": json.dumps(pomiar, ensure_ascii=False)})
        odpowiedz.raise_for_status()
        self.magazyn.zapisz_wynik({**odpowiedz.json(), "numer_probki": pomiar["numer_probki"]})
        self.kolejka.usun(wpis)
