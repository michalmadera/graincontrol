import asyncio

import pytest

from pomoc import SerwisTestowy, poczekaj_na, skalibrowany, nowy_cykl
from stacja.symulator import SymulatorMaszyny


async def poczekaj_na_ekran(cykl, ekran, limit=3.0):
    """Bez warunku „nic nie trwa”: do sprawdzania ekranów w trakcie ruchu."""
    async def petla():
        while cykl.opis()["ekran"] != ekran:
            await asyncio.sleep(0.001)
    await asyncio.wait_for(petla(), limit)


async def test_stop_zatrzymuje_ruch_i_pokazuje_ekran_zatrzymania(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, SerwisTestowy())
    cykl.akcja("nowy_pomiar")
    assert cykl.opis()["trwa"] is True
    await cykl.stop()
    assert maszyna.stan().webhooks == "shutdown"
    assert cykl.opis()["ekran"] == "zatrzymana"
    assert cykl.opis()["trwa"] is False


async def test_stop_w_trakcie_splywu_przerywa_tez_sterowanie_bez_makra(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, SerwisTestowy(), czas_splywu_s=1000)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("probka_wsypana")
    await poczekaj_na_ekran(cykl, "splyw")
    historia = list(maszyna.historia)
    await cykl.stop()
    await asyncio.sleep(0.01)
    assert maszyna.historia == historia, "po STOP żadne makro nie może już ruszyć"


async def test_po_stop_nic_nie_rusza_samo(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, SerwisTestowy())
    await cykl.stop()
    historia = list(maszyna.historia)
    await asyncio.sleep(0.05)
    assert maszyna.historia == historia
    assert cykl.opis()["ekran"] == "zatrzymana"


async def test_wznow_restartuje_ale_kalibracja_czeka_na_nacisniecie(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, SerwisTestowy())
    await cykl.stop()
    historia = list(maszyna.historia)
    cykl.akcja("wznow")
    await poczekaj_na(cykl, "kalibracja")
    await asyncio.sleep(0.02)
    assert maszyna.historia == historia
    assert maszyna.stan().skalibrowany is False


async def test_po_stop_w_cyklu_po_kalibracji_jest_czyszczenie(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, SerwisTestowy())
    cykl.akcja("nowy_pomiar")
    await cykl.stop()
    cykl.akcja("wznow")
    await poczekaj_na(cykl, "kalibracja")
    cykl.akcja("kalibruj")
    await poczekaj_na(cykl, "oproznij")
    assert maszyna.historia[-3:] == ["KALIBRUJ", "PRZYGOTUJ SZCZELINA=0.5", "POMIAR"]
    assert cykl.opis()["numer_probki"] is None


async def test_wznow_tylko_na_ekranie_zatrzymania(tmp_path):
    cykl, _ = await skalibrowany(tmp_path, SerwisTestowy())
    with pytest.raises(ValueError):
        cykl.akcja("wznow")


@pytest.mark.parametrize("makro", ["PRZYGOTUJ", "POMIAR"])
async def test_blad_makra_prowadzi_przez_odblokuj_kalibracje_i_czyszczenie(tmp_path, makro):
    cykl, maszyna = await skalibrowany(tmp_path, SerwisTestowy(), czas_splywu_s=0)
    maszyna.wymus_blad(makro, f"INTERLOCK: {makro}")
    cykl.akcja("nowy_pomiar")
    if makro == "POMIAR":
        await poczekaj_na(cykl, "wsyp")
        cykl.akcja("probka_wsypana")
    await poczekaj_na(cykl, "blad")
    assert maszyna.stan().zajety is True
    assert "Zabezpieczenie" in cykl.opis()["komunikat"]
    cykl.akcja("odblokuj")
    await poczekaj_na(cykl, "kalibracja")
    assert maszyna.historia[-1] == "ODBLOKUJ"
    cykl.akcja("kalibruj")
    await poczekaj_na(cykl, "oproznij")


async def test_nieudana_kalibracja_pokazuje_blad_a_nie_prosbe_o_kalibracje(tmp_path):
    cykl, maszyna = nowy_cykl(tmp_path)
    maszyna.wymus_blad("KALIBRUJ", "Klipper: brak oporu")
    cykl.akcja("kalibruj")
    await poczekaj_na(cykl, "blad")
    cykl.akcja("odblokuj")
    await poczekaj_na(cykl, "kalibracja")


async def test_blad_czyszczenia_nie_gubi_znacznika_brudnego_stolu(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, SerwisTestowy())
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("anuluj")
    maszyna.wymus_blad("POMIAR", "Klipper: awaria")
    cykl.akcja("kalibruj")
    await poczekaj_na(cykl, "blad")
    assert cykl.magazyn.brudny() is True


async def test_utrata_polaczenia_w_trakcie_makra_konczy_cykl_bledem(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, SerwisTestowy())
    cykl.akcja("nowy_pomiar")
    await asyncio.sleep(0)
    maszyna.rozlacz()
    await poczekaj_na_ekran(cykl, "brak_polaczenia")
    maszyna.polacz()
    await poczekaj_na(cykl, "blad")


def test_komunikat_robotnika_nie_zawiera_nazw_makr():
    from stacja.cykl import tekst_bledu
    for tresc in ["KALIBRUJ: osie nieskalibrowane - wykonaj KALIBRUJ.", "INTERLOCK: stol",
                  "POMIAR: system zajety (zajety=1).", "cokolwiek", "PRZYGOTUJ: SZCZELINA=9 za duza"]:
        tekst = tekst_bledu(tresc)
        assert not any(m in tekst for m in ("KALIBRUJ", "POMIAR", "PRZYGOTUJ", "ODBLOKUJ"))


async def test_stop_przy_braku_polaczenia_nie_wywraca_aplikacji(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, SerwisTestowy())

    async def awaria():
        raise OSError("brak sieci")
    maszyna.emergency_stop = awaria
    assert isinstance(await cykl.stop(), str)
    assert isinstance(maszyna, SymulatorMaszyny)
