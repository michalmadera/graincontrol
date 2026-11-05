import asyncio

import pytest

from pomoc import SerwisTestowy, nowy_cykl, poczekaj_na, skalibrowany
from stacja.magazyn import Magazyn


async def test_wejscie_i_wyjscie_z_trybu_serwisowego(tmp_path):
    cykl, _ = await skalibrowany(tmp_path)
    cykl.akcja("serwis_wejdz")
    assert cykl.opis()["ekran"] == "serwis"
    assert cykl.opis()["ustawienia"]["czas_splywu_s"] == 30
    cykl.akcja("serwis_wyjdz")
    assert cykl.opis()["ekran"] == "gotowa"


async def test_serwis_dostepny_bez_kalibracji_a_wyjscie_wraca_do_kalibracji(tmp_path):
    cykl, _ = nowy_cykl(tmp_path)
    cykl.akcja("serwis_wejdz")
    assert cykl.opis()["ekran"] == "serwis"
    cykl.akcja("serwis_wyjdz")
    assert cykl.opis()["ekran"] == "kalibracja"


async def test_serwisu_nie_ma_w_trakcie_pomiaru(tmp_path):
    cykl, _ = await skalibrowany(tmp_path)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    with pytest.raises(ValueError):
        cykl.akcja("serwis_wejdz")


async def test_ruch_reczny_idzie_z_listy_i_wymaga_trybu_serwisowego(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path)
    with pytest.raises(ValueError):
        cykl.akcja("serwis_ruch", {"ruch": "GORA_5MM"})
    cykl.akcja("serwis_wejdz")
    cykl.akcja("serwis_ruch", {"ruch": "GORA_5MM"})
    await poczekaj_na(cykl, "serwis")
    assert maszyna.historia[-1] == "GORA_5MM"
    with pytest.raises(ValueError):
        cykl.akcja("serwis_ruch", {"ruch": "MANUAL_STEPPER STEPPER=stol MOVE=300"})
    with pytest.raises(ValueError):
        cykl.akcja("serwis_ruch", {"ruch": "POMIAR"})


async def test_ruch_reczny_bez_kalibracji_daje_komunikat_bez_nazw_makr(tmp_path):
    cykl, maszyna = nowy_cykl(tmp_path)
    cykl.akcja("serwis_wejdz")
    cykl.akcja("serwis_ruch", {"ruch": "GORA_1MM"})
    await poczekaj_na(cykl, "serwis")
    assert "ustawienia" in cykl.opis()["komunikat"]
    assert maszyna.stan().zajety is False


async def test_ruch_reczny_po_wyjsciu_wymaga_nowego_przygotowania(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path)
    cykl.akcja("serwis_wejdz")
    cykl.akcja("serwis_ruch", {"ruch": "DOL_1MM"})
    await poczekaj_na(cykl, "serwis")
    cykl.akcja("serwis_wyjdz")
    assert cykl.opis()["ekran"] == "gotowa"
    assert maszyna.stan().przygotowany is False


async def test_zmiana_ustawien_jest_trwala(tmp_path):
    cykl, _ = await skalibrowany(tmp_path)
    cykl.akcja("serwis_wejdz")
    cykl.akcja("serwis_ustawienia", {"czas_splywu_s": 45, "szczelina_mm": 2.5, "skanowanie_wlaczone": True})
    assert Magazyn(tmp_path).ustawienia["czas_splywu_s"] == 45
    assert Magazyn(tmp_path).ustawienia["szczelina_mm"] == 2.5


@pytest.mark.parametrize("zmiana", [
    {"czas_splywu_s": -1}, {"szczelina_mm": 0.1}, {"szczelina_mm": "duza"}, {"limit_kolejki": 0},
    {"oproznianie_co_n": 0}, {"skanowanie_wlaczone": "tak"}, {"nieznane": 1},
])
async def test_zle_ustawienia_sa_odrzucane(tmp_path, zmiana):
    cykl, _ = await skalibrowany(tmp_path)
    cykl.akcja("serwis_wejdz")
    with pytest.raises(ValueError):
        cykl.akcja("serwis_ustawienia", zmiana)


async def test_reset_numeracji_tylko_z_potwierdzeniem(tmp_path):
    cykl, _ = await skalibrowany(tmp_path)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("anuluj")
    cykl.akcja("kalibruj")
    await poczekaj_na(cykl, "oproznij")
    cykl.akcja("oproznione")
    cykl.akcja("serwis_wejdz")
    with pytest.raises(ValueError):
        cykl.akcja("serwis_reset_numeracji", {})
    cykl.akcja("serwis_reset_numeracji", {"potwierdzam": True})
    assert cykl.opis()["nastepny_numer"] == 1


async def test_skanowanie_domyslnie_wylaczone(tmp_path):
    cykl, _ = await skalibrowany(tmp_path)
    assert cykl.opis()["skanowanie_wlaczone"] is False
    cykl.akcja("nowy_pomiar")
    assert cykl.opis()["numer_probki"] == 1


@pytest.mark.parametrize("kod", [None, "", "ABC", "ABCDE12345X", "ABCDE-1234", "ĄBCDE12345"])
async def test_wlaczone_skanowanie_wymaga_poprawnego_kodu(tmp_path, kod):
    cykl, _ = await skalibrowany(tmp_path, skanowanie_wlaczone=True)
    with pytest.raises(ValueError):
        cykl.akcja("nowy_pomiar", {"kod_partii": kod})
    assert cykl.opis()["nastepny_numer"] == 1, "odrzucony skan nie zużywa numeru"


async def test_kod_partii_trafia_do_metadanych_a_numer_nadal_rosnie(tmp_path):
    cykl, _ = await skalibrowany(tmp_path, SerwisTestowy(), skanowanie_wlaczone=True, czas_splywu_s=0)
    cykl.akcja("nowy_pomiar", {"kod_partii": "ABCDE12345"})
    assert cykl.opis()["numer_probki"] == 1
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("probka_wsypana")
    await poczekaj_na(cykl, "analiza")
    pomiar = cykl.kolejka.oczekujace()[0].pomiar
    assert pomiar["kod_partii"] == "ABCDE12345"
    assert pomiar["numer_probki"] == 1


async def test_wyjscie_z_serwisu_nie_omija_czyszczenia_brudnego_stolu(tmp_path):
    cykl, _ = await skalibrowany(tmp_path)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("anuluj")
    cykl.akcja("serwis_wejdz")
    cykl.akcja("serwis_wyjdz")
    assert cykl.opis()["ekran"] == "kalibracja"
    with pytest.raises(ValueError):
        cykl.akcja("nowy_pomiar")
