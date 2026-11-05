import json

from pomoc import SerwisTestowy, WYNIK, poczekaj_na, skalibrowany


async def do_analizy(tmp_path, serwis):
    cykl, maszyna = await skalibrowany(tmp_path, serwis, czas_splywu_s=0)
    cykl.wysylka.start()
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("probka_wsypana")
    return cykl, maszyna


async def test_wynik_trafia_na_ekran_a_kolejka_sie_oproznia(tmp_path):
    serwis = SerwisTestowy()
    cykl, _ = await do_analizy(tmp_path, serwis)
    await poczekaj_na(cykl, "wynik")
    await cykl.wysylka.stop()
    assert cykl.opis()["wynik"]["werdykt"] == WYNIK["werdykt"]
    assert cykl.kolejka.oczekujace() == []


async def test_wysylka_zawiera_png_dng_i_metadane(tmp_path):
    serwis = SerwisTestowy()
    cykl, _ = await do_analizy(tmp_path, serwis)
    await poczekaj_na(cykl, "wynik")
    await cykl.wysylka.stop()
    zadanie = serwis.zadania[0]
    assert zadanie.url.path == "/api/v1/pomiary"
    tresc = zadanie.content
    assert b'name="zdjecie"' in tresc and b'name="raw"' in tresc and b'name="metadane"' in tresc
    assert b'"numer_probki": 1' in tresc


async def test_po_dalej_ekran_wraca_do_gotowej_z_kolejnym_numerem(tmp_path):
    cykl, _ = await do_analizy(tmp_path, SerwisTestowy())
    await poczekaj_na(cykl, "wynik")
    cykl.akcja("dalej")
    await cykl.wysylka.stop()
    assert cykl.opis()["numer_probki"] is None
    assert cykl.opis()["nastepny_numer"] == 2


async def test_wynik_jest_zapisany_przed_usunieciem_zdjecia(tmp_path):
    cykl, _ = await do_analizy(tmp_path, SerwisTestowy())
    await poczekaj_na(cykl, "wynik")
    await cykl.wysylka.stop()
    stan = json.loads((tmp_path / "stan.json").read_text(encoding="utf-8"))
    assert stan["wyniki"][-1]["id_pomiaru"] == cykl.id_pomiaru
