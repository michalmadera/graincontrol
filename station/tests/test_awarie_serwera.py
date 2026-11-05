import asyncio

import httpx
import pytest

from pomoc import SerwisTestowy, poczekaj_na, skalibrowany


async def do_analizy(tmp_path, serwis, **ustawienia):
    cykl, maszyna = await skalibrowany(tmp_path, serwis, czas_splywu_s=0, **ustawienia)
    cykl.wysylka.start()
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("probka_wsypana")
    return cykl, maszyna


async def poczekaj(warunek, limit=3.0):
    async def petla():
        while not warunek():
            await asyncio.sleep(0.001)
    await asyncio.wait_for(petla(), limit)


def niedostepny(zadanie):
    raise httpx.ConnectError("brak")


async def test_brak_serwera_nie_gubi_zdjecia_i_po_powrocie_jest_wynik(tmp_path):
    serwis = SerwisTestowy(niedostepny)
    cykl, _ = await do_analizy(tmp_path, serwis)
    await poczekaj(lambda: cykl.opis()["serwer_dostepny"] is False)
    assert cykl.opis()["ekran"] == "analiza"
    assert cykl.opis()["w_kolejce"] == 1
    assert len(cykl.kolejka.oczekujace()) == 1
    serwis.odpowiedz = SerwisTestowy.sukces
    await poczekaj_na(cykl, "wynik")
    await cykl.wysylka.stop()
    assert cykl.opis()["serwer_dostepny"] is True
    assert cykl.opis()["w_kolejce"] == 0


@pytest.mark.parametrize("status", [500, 503])
async def test_blad_5xx_to_serwer_niedostepny_a_nie_utrata_zdjecia(tmp_path, status):
    serwis = SerwisTestowy(lambda z: httpx.Response(status))
    cykl, _ = await do_analizy(tmp_path, serwis)
    await poczekaj(lambda: len(serwis.zadania) >= 2)
    await cykl.wysylka.stop()
    assert len(cykl.kolejka.oczekujace()) == 1


async def test_mozna_isc_dalej_bez_wyniku_a_wynik_dochodzi_pozniej(tmp_path):
    serwis = SerwisTestowy(niedostepny)
    cykl, _ = await do_analizy(tmp_path, serwis)
    await poczekaj(lambda: cykl.opis()["serwer_dostepny"] is False)
    numer = cykl.opis()["numer_probki"]
    cykl.akcja("dalej_bez_wyniku")
    assert cykl.opis()["numer_probki"] is None
    serwis.odpowiedz = SerwisTestowy.sukces
    await poczekaj(lambda: cykl.opis()["w_kolejce"] == 0)
    await cykl.wysylka.stop()
    assert cykl.opis()["ostatnie_wyniki"][0]["numer_probki"] == numer


async def test_dalej_bez_wyniku_niedostepne_gdy_serwer_dziala(tmp_path):
    serwis = SerwisTestowy()
    cykl, _ = await skalibrowany(tmp_path, serwis, czas_splywu_s=0)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("probka_wsypana")
    await poczekaj_na(cykl, "analiza")
    with pytest.raises(ValueError):
        cykl.akcja("dalej_bez_wyniku")


async def test_odrzucenie_4xx_nie_blokuje_kolejki_i_mowi_o_serwisie(tmp_path):
    serwis = SerwisTestowy(lambda z: httpx.Response(400, json={"detail": "Zdjęcie nie jest plikiem PNG"}))
    cykl, _ = await do_analizy(tmp_path, serwis)
    await poczekaj_na(cykl, "wynik")
    await cykl.wysylka.stop()
    assert "PNG" in cykl.opis()["wynik"]["blad"]
    assert cykl.kolejka.oczekujace() == []
    assert len(list((tmp_path / "kolejka_odrzucone").iterdir())) == 1


async def test_pelna_kolejka_blokuje_nowy_pomiar_i_nic_nie_nadpisuje(tmp_path):
    serwis = SerwisTestowy(niedostepny)
    cykl, _ = await do_analizy(tmp_path, serwis, limit_kolejki=1)
    await poczekaj(lambda: cykl.opis()["serwer_dostepny"] is False)
    cykl.akcja("dalej_bez_wyniku")
    await poczekaj_na(cykl, "oproznij")
    cykl.akcja("oproznione")
    await cykl.wysylka.stop()
    assert cykl.opis()["kolejka_pelna"] is True
    with pytest.raises(ValueError):
        cykl.akcja("nowy_pomiar")
    assert len(cykl.kolejka.oczekujace()) == 1


async def test_uszkodzony_wpis_nie_zatrzymuje_wysylki(tmp_path):
    serwis = SerwisTestowy()
    cykl, _ = await do_analizy(tmp_path, serwis)
    await poczekaj_na(cykl, "wynik")
    wadliwy = cykl.kolejka.katalog / "00000099_wadliwy"
    wadliwy.mkdir()
    (wadliwy / "pomiar.json").write_text("{ nie json")
    cykl.wysylka.obudz()
    await poczekaj(lambda: cykl.kolejka.oczekujace() == [])
    await cykl.wysylka.stop()
    assert (tmp_path / "kolejka_odrzucone" / "00000099_wadliwy").exists()
