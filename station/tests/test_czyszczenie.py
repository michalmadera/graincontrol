import pytest

from pomoc import SerwisTestowy, poczekaj_na, skalibrowany
from stacja.magazyn import Magazyn


async def po_wyniku(tmp_path, **ustawienia):
    cykl, maszyna = await skalibrowany(tmp_path, SerwisTestowy(), czas_splywu_s=0, **ustawienia)
    cykl.wysylka.start()
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("probka_wsypana")
    await poczekaj_na(cykl, "wynik")
    return cykl, maszyna


async def test_po_wyniku_stol_jest_czyszczony_istniejacymi_makrami(tmp_path):
    cykl, maszyna = await po_wyniku(tmp_path)
    historia = len(maszyna.historia)
    cykl.akcja("dalej")
    assert cykl.opis()["ekran"] == "czyszczenie"
    await poczekaj_na(cykl, "oproznij")
    await cykl.wysylka.stop()
    assert maszyna.historia[historia:] == ["PRZYGOTUJ SZCZELINA=0.5", "POMIAR"]


async def test_czyszczenie_zawsze_na_waskiej_szczelinie_niezaleznie_od_pomiarowej(tmp_path):
    cykl, maszyna = await po_wyniku(tmp_path, szczelina_mm=2.5)
    assert "PRZYGOTUJ SZCZELINA=2.5" in maszyna.historia
    cykl.akcja("dalej")
    await poczekaj_na(cykl, "oproznij")
    await cykl.wysylka.stop()
    assert maszyna.historia[-2] == "PRZYGOTUJ SZCZELINA=0.5"


async def test_pudelko_blokuje_prace_az_do_potwierdzenia(tmp_path):
    cykl, _ = await po_wyniku(tmp_path)
    cykl.akcja("dalej")
    await poczekaj_na(cykl, "oproznij")
    with pytest.raises(ValueError):
        cykl.akcja("nowy_pomiar")
    cykl.akcja("oproznione")
    await cykl.wysylka.stop()
    assert cykl.opis()["ekran"] == "gotowa"


async def test_pudelko_co_n_czyszczen(tmp_path):
    cykl, _ = await po_wyniku(tmp_path, oproznianie_co_n=2)
    cykl.akcja("dalej")
    await poczekaj_na(cykl, "gotowa")
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("probka_wsypana")
    await poczekaj_na(cykl, "wynik")
    cykl.akcja("dalej")
    await poczekaj_na(cykl, "oproznij")
    await cykl.wysylka.stop()


async def test_blokada_pudelka_przezywa_restart(tmp_path):
    cykl, _ = await po_wyniku(tmp_path)
    cykl.akcja("dalej")
    await poczekaj_na(cykl, "oproznij")
    await cykl.wysylka.stop()
    assert Magazyn(tmp_path).czyszczen_od_oproznienia() == 1


async def test_anuluj_po_kalibracji_wymusza_czyszczenie(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, SerwisTestowy(), czas_splywu_s=0)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("anuluj")
    cykl.akcja("kalibruj")
    await poczekaj_na(cykl, "oproznij")
    assert maszyna.historia[-3:] == ["KALIBRUJ", "PRZYGOTUJ SZCZELINA=0.5", "POMIAR"]


async def test_czysty_stol_nie_wymaga_czyszczenia_po_kalibracji(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, SerwisTestowy())
    assert maszyna.historia == ["KALIBRUJ"]
    assert cykl.opis()["ekran"] == "gotowa"


async def test_znacznik_brudnego_stolu_ustawiony_przed_pierwszym_ruchem(tmp_path):
    cykl, _ = await skalibrowany(tmp_path, SerwisTestowy())
    cykl.akcja("nowy_pomiar")
    assert Magazyn(tmp_path).brudny() is True


async def test_znacznik_przezywa_restart_i_wymusza_czyszczenie(tmp_path):
    cykl, _ = await skalibrowany(tmp_path, SerwisTestowy())
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    await cykl.maszyna.firmware_restart()
    await poczekaj_na(cykl, "kalibracja")
    cykl.akcja("kalibruj")
    await poczekaj_na(cykl, "oproznij")
    assert Magazyn(tmp_path).brudny() is False
