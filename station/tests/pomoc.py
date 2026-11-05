import asyncio
import tempfile
from pathlib import Path

from stacja.cykl import Cykl
from stacja.kamera import Kamera
from stacja.kolejka import Kolejka
from stacja.magazyn import Magazyn
from stacja.symulator import SymulatorMaszyny

TEMPO = 0.001


def nowy_cykl(katalog=None, **ustawienia):
    katalog = Path(katalog or tempfile.mkdtemp())
    maszyna = SymulatorMaszyny(tempo=TEMPO)
    magazyn = Magazyn(katalog)
    if ustawienia:
        magazyn.zmien_ustawienia(ustawienia)
    cykl = Cykl(maszyna, magazyn, Kamera(katalog), Kolejka(katalog), tempo=TEMPO)
    return cykl, maszyna


async def poczekaj_na(cykl, ekran, limit=3.0):
    async def petla():
        while cykl.opis()["ekran"] != ekran or cykl.opis()["trwa"]:
            await asyncio.sleep(0.001)
    try:
        await asyncio.wait_for(petla(), limit)
    except asyncio.TimeoutError:
        raise AssertionError(f"Nie doszło do {ekran}, jest {cykl.opis()}")


async def skalibrowany(katalog=None, **ustawienia):
    cykl, maszyna = nowy_cykl(katalog, **ustawienia)
    cykl.akcja("kalibruj")
    await poczekaj_na(cykl, "gotowa")
    return cykl, maszyna
