import asyncio
import re
import tempfile
from pathlib import Path

import httpx

from stacja.cykl import Cykl
from stacja.kamera import Kamera
from stacja.kolejka import Kolejka
from stacja.magazyn import Magazyn
from stacja.symulator import SymulatorMaszyny
from stacja.wysylka import Wysylka

TEMPO = 0.001


WYNIK = {"werdykt": "akceptowalna", "liczba_kamieni": 1000, "liczba_wtracen": 10,
         "udzial_wtracen_proc": 1.0, "zrodlo_wyniku": "atrapa", "wersja_analizatora": "atrapa-1"}


class SerwisTestowy:
    """Zastępuje serwer analizy na poziomie HTTP; zachowanie można zmieniać w trakcie testu."""

    def __init__(self, odpowiedz=None):
        self.odpowiedz = odpowiedz or self.sukces
        self.zadania = []

    @staticmethod
    def sukces(zadanie):
        # Jak prawdziwy serwis: odsyła id pomiaru z metadanych.
        id_pomiaru = re.search(rb'"id_pomiaru": "([^"]+)"', zadanie.content).group(1).decode()
        return httpx.Response(200, json={**WYNIK, "id_pomiaru": id_pomiaru})

    def __call__(self, zadanie):
        self.zadania.append(zadanie)
        return self.odpowiedz(zadanie)


def nowy_cykl(katalog=None, serwis=None, **ustawienia):
    katalog = Path(katalog or tempfile.mkdtemp())
    maszyna = SymulatorMaszyny(tempo=TEMPO)
    magazyn = Magazyn(katalog)
    if ustawienia:
        magazyn.zmien_ustawienia(ustawienia)
    kolejka = Kolejka(katalog)
    transport = httpx.MockTransport(serwis or SerwisTestowy())
    wysylka = Wysylka(kolejka, magazyn, "http://serwis", transport=transport, tempo=TEMPO)
    cykl = Cykl(maszyna, magazyn, Kamera(katalog), kolejka, wysylka, tempo=TEMPO)
    return cykl, maszyna


async def poczekaj_na(cykl, ekran, limit=3.0):
    async def petla():
        while cykl.opis()["ekran"] != ekran or cykl.opis()["trwa"]:
            await asyncio.sleep(0.001)
    try:
        await asyncio.wait_for(petla(), limit)
    except asyncio.TimeoutError:
        raise AssertionError(f"Nie doszło do {ekran}, jest {cykl.opis()}")


async def skalibrowany(katalog=None, serwis=None, **ustawienia):
    cykl, maszyna = nowy_cykl(katalog, serwis, **ustawienia)
    cykl.akcja("kalibruj")
    await poczekaj_na(cykl, "gotowa")
    return cykl, maszyna
