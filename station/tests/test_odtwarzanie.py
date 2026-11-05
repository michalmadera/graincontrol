"""Restart backendu: maszyna (Klipper) żyje dalej i ma swój stan, stacja wstaje z dziennika."""
import httpx
import pytest

from pomoc import SerwisTestowy, TEMPO, poczekaj_na, skalibrowany
from stacja.cykl import Cykl
from stacja.kamera import Kamera
from stacja.kolejka import Kolejka
from stacja.magazyn import Magazyn
from stacja.wysylka import Wysylka


def po_restarcie(katalog, maszyna, serwis=None):
    magazyn, kolejka = Magazyn(katalog), Kolejka(katalog)
    wysylka = Wysylka(kolejka, magazyn, "http://serwis",
                      transport=httpx.MockTransport(serwis or SerwisTestowy()), tempo=TEMPO)
    return Cykl(maszyna, magazyn, Kamera(katalog), kolejka, wysylka, tempo=TEMPO)


async def test_czekanie_na_probke_wraca_na_ten_sam_ekran_z_tym_samym_numerem(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    nowy = po_restarcie(tmp_path, maszyna)
    assert nowy.opis()["ekran"] == "wsyp"
    assert nowy.opis()["numer_probki"] == 1


async def test_splyw_wraca_do_potwierdzenia_wsypania_bez_ruchu(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, czas_splywu_s=1000)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("probka_wsypana")
    historia = list(maszyna.historia)
    nowy = po_restarcie(tmp_path, maszyna)
    assert nowy.opis()["ekran"] == "wsyp"
    assert maszyna.historia == historia
    cykl._zadanie.cancel()


async def test_makro_w_toku_to_oczekiwanie_a_nie_blokada_i_bez_odblokuj(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path)
    cykl.akcja("nowy_pomiar")
    while not maszyna.stan().w_toku:
        await __import__("asyncio").sleep(0)
    nowy = po_restarcie(tmp_path, maszyna)
    assert nowy.opis()["ekran"] == "oczekiwanie"
    with pytest.raises(ValueError):
        nowy.akcja("odblokuj")
    assert "ODBLOKUJ" not in maszyna.historia
    await poczekaj_na(cykl, "wsyp")     # stare zadanie to działające makro Klippera
    assert nowy.opis()["ekran"] == "kalibracja", "wyniku makra nie znamy, więc cykl jest przerwany"


async def test_zablokowana_maszyna_po_restarcie_pokazuje_blad(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path)
    maszyna.wymus_blad("PRZYGOTUJ", "INTERLOCK")
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "blad")
    nowy = po_restarcie(tmp_path, maszyna)
    assert nowy.opis()["ekran"] == "blad"
    assert nowy.opis()["komunikat"]
    nowy.akcja("odblokuj")
    await poczekaj_na(nowy, "kalibracja")
    nowy.akcja("kalibruj")
    await poczekaj_na(nowy, "oproznij")


async def test_zdjecie_przerwane_restartem_mozna_ponowic_bez_ruchu(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, czas_splywu_s=0)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("probka_wsypana")
    await poczekaj_na(cykl, "analiza")
    magazyn = Magazyn(tmp_path)
    magazyn.zapisz_cykl({**magazyn.cykl(), "krok": "zdjecie"})
    for wpis in cykl.kolejka.oczekujace():
        cykl.kolejka.usun(wpis)
    nowy = po_restarcie(tmp_path, maszyna)
    assert nowy.opis()["ekran"] == "blad_zdjecia"
    nowy.akcja("ponow_zdjecie")
    await poczekaj_na(nowy, "analiza")
    assert len(nowy.kolejka.oczekujace()) == 1


async def test_zdjecie_juz_w_kolejce_nie_jest_robione_drugi_raz(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, czas_splywu_s=0)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("probka_wsypana")
    await poczekaj_na(cykl, "analiza")
    magazyn = Magazyn(tmp_path)
    magazyn.zapisz_cykl({**magazyn.cykl(), "krok": "zdjecie"})
    nowy = po_restarcie(tmp_path, maszyna)
    assert nowy.opis()["ekran"] == "analiza"


async def test_analiza_i_wynik_przezywaja_restart(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, czas_splywu_s=0)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("probka_wsypana")
    await poczekaj_na(cykl, "analiza")
    nowy = po_restarcie(tmp_path, maszyna)
    assert nowy.opis()["ekran"] == "analiza"
    nowy.wysylka.start()
    await poczekaj_na(nowy, "wynik")
    await nowy.wysylka.stop()
    trzeci = po_restarcie(tmp_path, maszyna)
    assert trzeci.opis()["ekran"] == "wynik"
    assert trzeci.opis()["wynik"]["werdykt"]


async def test_maszyna_bez_kalibracji_po_restarcie_wymusza_kalibracje_i_czyszczenie(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    await maszyna.firmware_restart()
    nowy = po_restarcie(tmp_path, maszyna)
    assert nowy.opis()["ekran"] == "kalibracja"
    nowy.akcja("kalibruj")
    await poczekaj_na(nowy, "oproznij")


async def test_reczny_ruch_stolu_uniewaznia_czekanie_na_probke(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    await maszyna.wywolaj("DOL_1MM")
    assert cykl.opis()["ekran"] == "kalibracja"
