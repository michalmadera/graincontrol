"""Automat cyklu: jedyne miejsce, które decyduje, który ekran widzi robotnik."""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone

from .kamera import BladZdjecia, Kamera
from .kolejka import Kolejka
from .magazyn import Magazyn
from .maszyna import BladMakra, BrakPolaczenia, Maszyna
from .wysylka import Wysylka


class Cykl:
    def __init__(self, maszyna: Maszyna, magazyn: Magazyn, kamera: Kamera, kolejka: Kolejka,
                 wysylka: Wysylka, tempo: float = 1.0) -> None:
        self.maszyna = maszyna
        self.magazyn = magazyn
        self.kamera = kamera
        self.kolejka = kolejka
        self.wysylka = wysylka
        self.tempo = tempo
        self.krok = "gotowa"
        self.numer_probki: int | None = None
        self.id_pomiaru: str | None = None
        self.komunikat: str | None = None
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

    def _odbierz_wynik(self) -> None:
        if self.krok == "analiza" and not self.trwa and self.magazyn.wynik(self.id_pomiaru):
            self.krok = "wynik"

    def opis(self) -> dict:
        self._odbierz_wynik()
        pozostalo = None
        if self._koniec_splywu is not None:
            pozostalo = max(0, round((self._koniec_splywu - time.monotonic()) / self.tempo))
        return {
            "ekran": self._ekran(),
            "trwa": self.trwa,
            "numer_probki": self.numer_probki,
            "nastepny_numer": self.magazyn.nastepny_numer(),
            "pozostalo_s": pozostalo,
            "komunikat": self.komunikat,
            "wynik": self.magazyn.wynik(self.id_pomiaru) if self.krok == "wynik" else None,
        }

    def akcja(self, nazwa: str) -> None:
        obsluga = {
            "kalibruj": self._kalibruj,
            "nowy_pomiar": self._nowy_pomiar,
            "probka_wsypana": self._probka_wsypana,
            "anuluj": self._anuluj,
            "ponow_zdjecie": self._ponow_zdjecie,
            "dalej": self._dalej,
        }.get(nazwa)
        if obsluga is None:
            raise ValueError(f"Nieznana akcja: {nazwa}")
        if self.trwa:
            raise ValueError("Maszyna pracuje")
        self._odbierz_wynik()
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
        self.id_pomiaru = str(uuid.uuid4())
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
        await self._zrob_zdjecie()

    async def _zrob_zdjecie(self) -> None:
        self.krok = "zdjecie"
        self.komunikat = None
        try:
            zdjecie = await self.kamera.zrob(self.numer_probki)
            self.kolejka.dodaj(zdjecie, {
                "id_pomiaru": self.id_pomiaru,
                "numer_probki": self.numer_probki,
                "id_stacji": self.magazyn.ustawienia["id_stacji"],
                "czas_zdjecia": datetime.now(timezone.utc).isoformat(),
            })
        except BladZdjecia as exc:
            self.krok = "blad_zdjecia"
            self.komunikat = str(exc)
            return
        self.krok = "analiza"
        self.wysylka.obudz()

    def _ponow_zdjecie(self) -> None:
        self._wymagaj("blad_zdjecia")
        self.krok = "zdjecie"
        self._uruchom(self._zrob_zdjecie())

    def _dalej(self) -> None:
        self._wymagaj("wynik")
        self.numer_probki = None
        self.id_pomiaru = None
        self.krok = "gotowa"

    def _anuluj(self) -> None:
        self._wymagaj("wsyp")
        self.numer_probki = None
        self.id_pomiaru = None
        # Robotnik nacisnął „Anuluj”, a nie kalibrację: maszyna rusza dopiero po drugim przycisku.
        self.krok = "kalibracja"
