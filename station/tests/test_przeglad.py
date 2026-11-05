"""Scenariusze z niezależnego przeglądu kodu: każdy zawieszał ekran albo gubił dane."""
import asyncio
import json

import httpx
import pytest

from atrapa_moonrakera import AtrapaMoonrakera
from pomoc import SerwisTestowy, TEMPO, WYNIK, nowy_cykl, poczekaj_na, skalibrowany
from stacja.config import Konfiguracja
from stacja.cykl import Cykl
from stacja.kamera import Kamera
from stacja.kolejka import Kolejka
from stacja.magazyn import Magazyn
from stacja.maszyna import BrakPolaczenia
from stacja.moonraker import MoonrakerMaszyna
from stacja.wysylka import Wysylka
from test_moonraker import poczekaj


async def do_wsypu(cykl):
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")


def niedostepny(zadanie):
    raise httpx.ConnectError("brak")


# ------------------------------------------------------------------ STOP
async def test_nieudany_stop_jest_widoczny_i_ponawiany_do_skutku(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path)
    prawdziwy = maszyna.emergency_stop

    async def awaria():
        raise BrakPolaczenia("brak")
    maszyna.emergency_stop = awaria
    assert await cykl.stop() == "brak_polaczenia"
    assert cykl.opis()["stop_nieudany"] is True
    with pytest.raises(ValueError):
        cykl.akcja("serwis_wejdz")
    maszyna.emergency_stop = prawdziwy
    await poczekaj(lambda: cykl.opis()["stop_nieudany"] is False)
    assert maszyna.stan().webhooks == "shutdown"


async def test_nieudany_stop_nie_zostawia_ekranu_ruchu_bez_przyciskow(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, czas_splywu_s=1000)
    await do_wsypu(cykl)
    cykl.akcja("probka_wsypana")

    async def awaria():
        raise BrakPolaczenia("brak")
    maszyna.emergency_stop = awaria
    await cykl.stop()
    assert cykl.opis()["ekran"] == "kalibracja"
    assert cykl.magazyn.brudny() is True
    cykl._ponawianie_stop.cancel()


async def test_stop_poza_cyklem_tez_wymusza_czyszczenie(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path)
    await cykl.stop()
    cykl.akcja("wznow")
    await poczekaj_na(cykl, "kalibracja")
    cykl.akcja("kalibruj")
    await poczekaj_na(cykl, "oproznij")
    assert maszyna.historia[-3:] == ["KALIBRUJ", "PRZYGOTUJ SZCZELINA=0.5", "POMIAR"]


# ------------------------------------------------------------------ makro po zerwaniu połączenia
async def test_zerwanie_polaczenia_nie_pokazuje_bledu_nad_ruszajaca_maszyna(tmp_path):
    atrapa = AtrapaMoonrakera(czas_makra=0.3)
    await atrapa.start()
    maszyna = MoonrakerMaszyna(atrapa.adres, odstep_ponowien=0.01)
    await maszyna.start()
    await poczekaj(lambda: maszyna.stan().polaczona)
    magazyn, kolejka = Magazyn(tmp_path), Kolejka(tmp_path)
    cykl = Cykl(maszyna, magazyn, Kamera(tmp_path), kolejka,
                Wysylka(kolejka, magazyn, "http://serwis", tempo=TEMPO), tempo=TEMPO)
    cykl.akcja("kalibruj")
    await poczekaj(lambda: maszyna.stan().w_toku)
    for klient in list(atrapa.klienci):
        await klient.close()
    await poczekaj(lambda: cykl.opis()["ekran"] == "oczekiwanie")
    assert "ODBLOKUJ" not in atrapa.skrypty
    with pytest.raises(ValueError):
        cykl.akcja("odblokuj")
    await poczekaj(lambda: cykl.opis()["ekran"] == "blad")
    await maszyna.stop()
    await atrapa.stop()


async def test_opoznione_flagi_nie_daja_falszywych_ekranow(tmp_path):
    """Klipper wysyła stan co ok. 250 ms, więc flagi mogą dojść po odpowiedzi makra."""
    atrapa = AtrapaMoonrakera(czas_makra=0.01, opoznienie_statusu=0.1)
    await atrapa.start()
    maszyna = MoonrakerMaszyna(atrapa.adres, odstep_ponowien=0.01)
    await maszyna.start()
    await poczekaj(lambda: maszyna.stan().polaczona)
    magazyn, kolejka = Magazyn(tmp_path), Kolejka(tmp_path)
    cykl = Cykl(maszyna, magazyn, Kamera(tmp_path), kolejka,
                Wysylka(kolejka, magazyn, "http://serwis"), tempo=1.0)
    widziane = set()

    async def obserwuj(cel):
        while cykl.opis()["ekran"] != cel or cykl.opis()["trwa"]:
            widziane.add(cykl.opis()["ekran"])
            await asyncio.sleep(0.002)
    cykl.akcja("kalibruj")
    await asyncio.wait_for(obserwuj("gotowa"), 3)
    assert "blad" not in widziane
    widziane.clear()
    await asyncio.sleep(0.15)
    cykl.akcja("nowy_pomiar")
    await asyncio.wait_for(obserwuj("wsyp"), 3)
    assert not widziane & {"blad", "kalibracja"}
    await maszyna.stop()
    await atrapa.stop()


async def test_klipper_w_stanie_error_mozna_wznowic(tmp_path):
    atrapa = AtrapaMoonrakera()
    atrapa.webhooks = {"state": "error", "state_message": "Lost communication with MCU"}
    await atrapa.start()
    maszyna = MoonrakerMaszyna(atrapa.adres, odstep_ponowien=0.01)
    await maszyna.start()
    await poczekaj(lambda: maszyna.stan().polaczona)
    magazyn, kolejka = Magazyn(tmp_path), Kolejka(tmp_path)
    cykl = Cykl(maszyna, magazyn, Kamera(tmp_path), kolejka,
                Wysylka(kolejka, magazyn, "http://serwis", tempo=TEMPO), tempo=TEMPO)
    assert cykl.opis()["ekran"] == "zatrzymana"
    assert "Lost communication" in cykl.opis()["komunikat_maszyny"]
    cykl.akcja("wznow")
    await poczekaj(lambda: cykl.opis()["ekran"] == "kalibracja")
    await maszyna.stop()
    await atrapa.stop()


async def test_po_rozlaczeniu_klippera_stan_jest_odpytywany_bez_powiadomienia_ready(tmp_path):
    atrapa = AtrapaMoonrakera()
    await atrapa.start()
    maszyna = MoonrakerMaszyna(atrapa.adres, odstep_ponowien=0.01)
    await maszyna.start()
    await poczekaj(lambda: maszyna.stan().polaczona)
    atrapa.webhooks = {"state": "startup", "state_message": ""}
    await atrapa.rozeslij("notify_klippy_disconnected")
    await poczekaj(lambda: maszyna.stan().webhooks == "startup")
    atrapa.webhooks = {"state": "error", "state_message": "awaria"}      # bez notify_klippy_ready
    await poczekaj(lambda: maszyna.stan().webhooks == "error")
    await maszyna.stop()
    await atrapa.stop()


# ------------------------------------------------------------------ wysyłka
@pytest.mark.parametrize("odpowiedz", [
    httpx.Response(200, text="<html>proxy</html>"),
    httpx.Response(200, json=[1, 2]),
    httpx.Response(200, json={"status": "ok"}),
    httpx.Response(200, json={**WYNIK, "id_pomiaru": "inny"}),
    httpx.Response(302, headers={"location": "/login"}),
])
async def test_zla_odpowiedz_200_lub_3xx_nie_kasuje_zdjecia_i_nie_zabija_wysylki(tmp_path, odpowiedz):
    serwis = SerwisTestowy(lambda z: odpowiedz)
    cykl, _ = await skalibrowany(tmp_path, serwis, czas_splywu_s=0)
    cykl.wysylka.start()
    await do_wsypu(cykl)
    cykl.akcja("probka_wsypana")
    await poczekaj(lambda: len(serwis.zadania) >= 2 and cykl.opis()["serwer_dostepny"] is False)
    assert len(cykl.kolejka.oczekujace()) == 1
    assert cykl.opis()["ostatnie_wyniki"] == []
    serwis.odpowiedz = SerwisTestowy.sukces
    await poczekaj_na(cykl, "wynik")
    await cykl.wysylka.stop()


@pytest.mark.parametrize("status", [404, 408, 413, 429])
async def test_inne_4xx_to_serwer_niedostepny_a_nie_odrzucenie_zdjecia(tmp_path, status):
    serwis = SerwisTestowy(lambda z: httpx.Response(status))
    cykl, _ = await skalibrowany(tmp_path, serwis, czas_splywu_s=0)
    cykl.wysylka.start()
    await do_wsypu(cykl)
    cykl.akcja("probka_wsypana")
    await poczekaj(lambda: len(serwis.zadania) >= 2)
    await cykl.wysylka.stop()
    assert len(cykl.kolejka.oczekujace()) == 1


async def test_nieoczekiwany_wyjatek_nie_zabija_wysylki(tmp_path, monkeypatch):
    serwis = SerwisTestowy()
    cykl, _ = await skalibrowany(tmp_path, serwis, czas_splywu_s=0)
    pierwszy = {"raz": True}
    prawdziwy = cykl.magazyn.zapisz_wynik

    def brak_miejsca(wynik):
        if pierwszy["raz"]:
            pierwszy["raz"] = False
            raise OSError(28, "No space left on device")
        prawdziwy(wynik)
    monkeypatch.setattr(cykl.magazyn, "zapisz_wynik", brak_miejsca)
    cykl.wysylka.start()
    await do_wsypu(cykl)
    cykl.akcja("probka_wsypana")
    await poczekaj_na(cykl, "wynik")
    await cykl.wysylka.stop()


async def test_uszkodzony_biezacy_pomiar_konczy_analize_komunikatem(tmp_path):
    cykl, _ = await skalibrowany(tmp_path, SerwisTestowy(), czas_splywu_s=0)
    await do_wsypu(cykl)
    cykl.akcja("probka_wsypana")
    await poczekaj_na(cykl, "analiza")
    (cykl.kolejka.oczekujace()[0].katalog / "pomiar.json").write_text("{ nie json")
    cykl.wysylka.start()
    await poczekaj_na(cykl, "wynik")
    await cykl.wysylka.stop()
    assert cykl.opis()["wynik"]["blad"]


async def test_duza_kolejka_pozwala_isc_dalej_gdy_serwer_dziala(tmp_path):
    serwis = SerwisTestowy(niedostepny)
    cykl, _ = await skalibrowany(tmp_path, serwis, czas_splywu_s=0)
    await do_wsypu(cykl)
    cykl.akcja("probka_wsypana")
    await poczekaj_na(cykl, "analiza")
    assert cykl.opis()["mozna_dalej"] is False, "własna próbka jest pierwsza, serwer rzekomo działa"
    pierwszy = cykl.kolejka.oczekujace()[0]
    kopia = cykl.kolejka.katalog / "00000000_wczesniejszy"
    kopia.mkdir()
    (kopia / "pomiar.json").write_text(json.dumps({**pierwszy.pomiar, "id_pomiaru": "wczesniejszy"}))
    assert cykl.opis()["mozna_dalej"] is True
    cykl.akcja("dalej_bez_wyniku")
    assert cykl.opis()["ekran"] == "czyszczenie"


async def test_ponowny_zapis_wyniku_nie_robi_duplikatu(tmp_path):
    magazyn = Magazyn(tmp_path)
    magazyn.zapisz_wynik({"id_pomiaru": "a", "werdykt": "akceptowalna"})
    magazyn.zapisz_wynik({"id_pomiaru": "a", "werdykt": "akceptowalna"})
    assert len(magazyn.ostatnie_wyniki()) == 1


async def test_widac_piec_ostatnich_wynikow_a_zapis_pomiesci_cala_kolejke(tmp_path):
    magazyn = Magazyn(tmp_path)
    for i in range(60):
        magazyn.zapisz_wynik({"id_pomiaru": str(i), "numer_probki": i})
    assert [w["numer_probki"] for w in magazyn.ostatnie_wyniki()] == [59, 58, 57, 56, 55]
    assert magazyn.wynik("0") is not None


# ------------------------------------------------------------------ zadania cyklu
async def test_blad_dysku_przy_zdjeciu_daje_ponowienie_a_nie_wieczny_ekran(tmp_path, monkeypatch):
    cykl, _ = await skalibrowany(tmp_path, czas_splywu_s=0)

    def brak_miejsca(zdjecie, pomiar):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(cykl.kolejka, "dodaj", brak_miejsca)
    await do_wsypu(cykl)
    cykl.akcja("probka_wsypana")
    await poczekaj_na(cykl, "blad_zdjecia")


async def test_nieudane_dodanie_nie_zostawia_niekompletnego_wpisu(tmp_path, monkeypatch):
    cykl, _ = await skalibrowany(tmp_path, czas_splywu_s=0)
    await do_wsypu(cykl)
    zdjecie = await cykl.kamera.zrob(1)
    monkeypatch.setattr("stacja.kolejka.json.dump", lambda *a, **k: (_ for _ in ()).throw(OSError(28, "brak")))
    with pytest.raises(OSError):
        cykl.kolejka.dodaj(zdjecie, {"id_pomiaru": "x"})
    assert list(cykl.kolejka.katalog.iterdir()) == []


async def test_nieoczekiwany_wyjatek_w_zadaniu_pokazuje_blad(tmp_path, monkeypatch):
    cykl, maszyna = await skalibrowany(tmp_path)

    async def wybuch(makro):
        raise KeyError("niespodzianka")
    monkeypatch.setattr(maszyna, "wywolaj", wybuch)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "blad")


async def test_zdjecie_mozna_porzucic_a_stol_zostaje_wyczyszczony(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, czas_splywu_s=0)
    cykl.kamera.wymus_blad("awaria")
    await do_wsypu(cykl)
    cykl.akcja("probka_wsypana")
    await poczekaj_na(cykl, "blad_zdjecia")
    cykl.akcja("porzuc_zdjecie")
    await poczekaj_na(cykl, "oproznij")
    assert cykl.opis()["numer_probki"] is None


async def test_serwis_z_ekranu_bledu_zdjecia_resetuje_odniesienie_i_wraca(tmp_path):
    cykl, _ = await skalibrowany(tmp_path, czas_splywu_s=0)
    cykl.kamera.wymus_blad("awaria")
    await do_wsypu(cykl)
    cykl.akcja("probka_wsypana")
    await poczekaj_na(cykl, "blad_zdjecia")
    cykl.kamera.kontroler.reference["reference_ccm"] = [1.0]
    cykl.akcja("serwis_wejdz")
    cykl.akcja("serwis_reset_odniesienia")
    assert cykl.kamera.kontroler.reference["reference_ccm"] is None
    cykl.akcja("serwis_wyjdz")
    assert cykl.opis()["ekran"] == "blad_zdjecia"
    cykl.akcja("ponow_zdjecie")
    await poczekaj_na(cykl, "analiza")


async def test_odrzucenie_przez_kontrakt_mowi_po_ludzku(tmp_path, monkeypatch):
    kamera = Kamera(tmp_path)

    async def odrzucone():
        return {"accepted": False, "violations": ["ColourCorrectionMatrix: zmierzone 1, profil 2"]}
    monkeypatch.setattr(kamera.kontroler, "shoot", odrzucone)
    with pytest.raises(Exception) as blad:
        await kamera.zrob(1)
    assert "ColourCorrectionMatrix" not in str(blad.value)


# ------------------------------------------------------------------ konfiguracja
def test_domyslnie_nie_ma_symulatora_ani_sterowania_dev(monkeypatch):
    from stacja.config import wczytaj
    monkeypatch.delenv("STACJA_MASZYNA", raising=False)
    assert wczytaj().maszyna == "moonraker"


def test_maszyna_z_atrapa_kamery_nie_startuje_bez_jawnej_zgody(tmp_path):
    from stacja.main import create_app
    konf = dict(maszyna="moonraker", tempo=1.0, dane=tmp_path, serwis="http://x")
    with pytest.raises(RuntimeError, match="atrapa kamery"):
        create_app(Konfiguracja(**konf))
    create_app(Konfiguracja(**konf, atrapa_kamery_dozwolona=True))


async def test_nowy_cykl_helper_nadal_dziala():
    cykl, _ = nowy_cykl()
    assert cykl.opis()["stop_nieudany"] is False
