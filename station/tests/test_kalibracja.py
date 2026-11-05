import asyncio

import pytest

from pomoc import nowy_cykl, poczekaj_na
from stacja.maszyna import BladMakra, MakroNiedozwolone, sprawdz_makro
from stacja.symulator import SymulatorMaszyny


async def test_swiezy_start_wymaga_kalibracji():
    cykl, _ = nowy_cykl()
    assert cykl.opis()["ekran"] == "kalibracja"
    assert cykl.opis()["trwa"] is False


async def test_kalibracja_startuje_dopiero_po_akcji_i_prowadzi_do_gotowej():
    cykl, maszyna = nowy_cykl()
    await asyncio.sleep(0.01)
    assert maszyna.stan().skalibrowany is False, "nie wolno ruszać bez naciśnięcia"
    cykl.akcja("kalibruj")
    await poczekaj_na(cykl, "gotowa")
    assert maszyna.stan().skalibrowany is True


async def test_restart_maszyny_zawsze_wraca_do_kalibracji():
    cykl, maszyna = nowy_cykl()
    cykl.akcja("kalibruj")
    await poczekaj_na(cykl, "gotowa")
    await maszyna.firmware_restart()
    await poczekaj_na(cykl, "kalibracja")


async def test_utrata_polaczenia_pokazuje_brak_polaczenia():
    cykl, maszyna = nowy_cykl()
    maszyna.rozlacz()
    assert cykl.opis()["ekran"] == "brak_polaczenia"
    maszyna.polacz()
    assert cykl.opis()["ekran"] == "kalibracja"


async def test_akcji_nie_ma_na_niewlasciwym_ekranie():
    cykl, _ = nowy_cykl()
    with pytest.raises(ValueError):
        cykl.akcja("nieistniejaca")


@pytest.mark.parametrize("makro", [
    "MANUAL_STEPPER STEPPER=stol MOVE=300", "_RUCH_SPYCHACZ S=405", "G28",
    "KALIBRUJ\nMANUAL_STEPPER STEPPER=stol MOVE=300", "PRZYGOTUJ SZCZELINA=-1", "",
])
def test_makra_spoza_listy_sa_odrzucane(makro):
    with pytest.raises(MakroNiedozwolone):
        sprawdz_makro(makro)


@pytest.mark.parametrize("makro", [
    "KALIBRUJ", "PRZYGOTUJ", "PRZYGOTUJ SZCZELINA=0.5", "POMIAR", "ODBLOKUJ",
    "STAN_SYSTEMU", "GORA_5MM", "DOL_1MM",
])
def test_makra_z_listy_przechodza(makro):
    assert sprawdz_makro(makro) == makro


async def test_symulator_odrzuca_makro_spoza_listy_przed_wykonaniem():
    maszyna = SymulatorMaszyny(tempo=0.001)
    with pytest.raises(MakroNiedozwolone):
        await maszyna.wywolaj("_RUCH_STOL T=300")


async def test_symulator_jak_klipper_zostawia_blokade_po_bledzie():
    maszyna = SymulatorMaszyny(tempo=0.001)
    maszyna.wymus_blad("KALIBRUJ", "Klipper: brak oporu")
    with pytest.raises(BladMakra):
        await maszyna.wywolaj("KALIBRUJ")
    assert maszyna.stan().zajety is True
