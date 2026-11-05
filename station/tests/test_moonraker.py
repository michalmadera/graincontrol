import asyncio

import pytest
import pytest_asyncio

from atrapa_moonrakera import AtrapaMoonrakera
from pomoc import poczekaj_na
from stacja.cykl import Cykl
from stacja.kamera import Kamera
from stacja.kolejka import Kolejka
from stacja.magazyn import Magazyn
from stacja.maszyna import BladMakra, BrakPolaczenia, MakroNiedozwolone
from stacja.moonraker import MoonrakerMaszyna
from stacja.wysylka import Wysylka


@pytest_asyncio.fixture
async def uklad():
    atrapa = AtrapaMoonrakera()
    await atrapa.start()
    maszyna = MoonrakerMaszyna(atrapa.adres, odstep_ponowien=0.01)
    await maszyna.start()
    await poczekaj(lambda: maszyna.stan().polaczona)
    yield atrapa, maszyna
    await maszyna.stop()
    await atrapa.stop()


async def poczekaj(warunek, limit=3.0):
    async def petla():
        while not warunek():
            await asyncio.sleep(0.002)
    await asyncio.wait_for(petla(), limit)


async def test_po_polaczeniu_zna_stan_maszyny(uklad):
    _, maszyna = uklad
    stan = maszyna.stan()
    assert stan.webhooks == "ready"
    assert stan.skalibrowany is False and stan.zajety is False


async def test_makro_czeka_na_koniec_a_flagi_przychodza_powiadomieniami(uklad):
    atrapa, maszyna = uklad
    zadanie = asyncio.create_task(maszyna.wywolaj("KALIBRUJ"))
    await poczekaj(lambda: maszyna.stan().zajety)
    assert maszyna.stan().w_toku is True
    assert not zadanie.done()
    await zadanie
    await poczekaj(lambda: maszyna.stan().skalibrowany)
    assert maszyna.stan().zajety is False
    assert atrapa.skrypty == ["KALIBRUJ"]


async def test_blad_makra_ma_tresc_z_klippera(uklad):
    _, maszyna = uklad
    with pytest.raises(BladMakra, match="osie nieskalibrowane"):
        await maszyna.wywolaj("PRZYGOTUJ")


async def test_makro_spoza_listy_nie_dociera_do_serwera(uklad):
    atrapa, maszyna = uklad
    with pytest.raises(MakroNiedozwolone):
        await maszyna.wywolaj("MANUAL_STEPPER STEPPER=stol MOVE=300")
    assert atrapa.skrypty == []


async def test_stop_dziala_w_trakcie_makra_i_zmienia_stan(uklad):
    atrapa, maszyna = uklad
    atrapa.czas_makra = 0.2
    zadanie = asyncio.create_task(maszyna.wywolaj("KALIBRUJ"))
    await poczekaj(lambda: maszyna.stan().zajety)
    await maszyna.emergency_stop()
    await poczekaj(lambda: maszyna.stan().webhooks == "shutdown")
    with pytest.raises(BladMakra):
        await zadanie


async def test_restart_kasuje_flagi_i_wraca_do_gotowosci(uklad):
    atrapa, maszyna = uklad
    await maszyna.wywolaj("KALIBRUJ")
    await poczekaj(lambda: maszyna.stan().skalibrowany)
    await maszyna.emergency_stop()
    await maszyna.firmware_restart()
    await poczekaj(lambda: maszyna.stan().webhooks == "ready")
    assert maszyna.stan().skalibrowany is False


async def test_zerwanie_w_trakcie_makra_to_brak_polaczenia_a_potem_powrot(uklad):
    atrapa, maszyna = uklad
    atrapa.czas_makra = 0.5
    zadanie = asyncio.create_task(maszyna.wywolaj("KALIBRUJ"))
    await poczekaj(lambda: maszyna.stan().zajety)
    polaczenia = atrapa.polaczenia
    for klient in list(atrapa.klienci):
        await klient.close()
    with pytest.raises(BrakPolaczenia):
        await zadanie
    await poczekaj(lambda: atrapa.polaczenia > polaczenia and maszyna.stan().polaczona)


async def test_wywolanie_bez_polaczenia_nie_czeka_w_nieskonczonosc():
    maszyna = MoonrakerMaszyna("ws://127.0.0.1:9/websocket", odstep_ponowien=0.01)
    await maszyna.start()
    assert maszyna.stan().polaczona is False
    with pytest.raises(BrakPolaczenia):
        await maszyna.wywolaj("KALIBRUJ")
    with pytest.raises(BrakPolaczenia):
        await maszyna.emergency_stop()
    await maszyna.stop()


async def test_cykl_bez_zmian_dziala_przez_moonrakera(uklad, tmp_path):
    atrapa, maszyna = uklad
    magazyn, kolejka = Magazyn(tmp_path), Kolejka(tmp_path)
    magazyn.zmien_ustawienia({"czas_splywu_s": 0})
    cykl = Cykl(maszyna, magazyn, Kamera(tmp_path), kolejka,
                Wysylka(kolejka, magazyn, "http://serwis", tempo=0.001), tempo=0.001)
    assert cykl.opis()["ekran"] == "kalibracja"
    cykl.akcja("kalibruj")
    await poczekaj_na(cykl, "gotowa")
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("probka_wsypana")
    await poczekaj_na(cykl, "analiza")
    assert atrapa.skrypty == ["KALIBRUJ", "PRZYGOTUJ", "POMIAR"]
