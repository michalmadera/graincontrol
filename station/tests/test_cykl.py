import pytest

from pomoc import nowy_cykl, poczekaj_na, skalibrowany
from stacja.magazyn import Magazyn


async def test_pelny_przebieg_do_rozgarniecia(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, czas_splywu_s=1)
    cykl.akcja("nowy_pomiar")
    assert cykl.opis()["ekran"] == "przygotowanie"
    await poczekaj_na(cykl, "wsyp")
    assert maszyna.stan().przygotowany is True
    cykl.akcja("probka_wsypana")
    assert cykl.opis()["ekran"] == "splyw"
    await poczekaj_na(cykl, "zdjecie")
    assert maszyna.historia == ["KALIBRUJ", "PRZYGOTUJ", "POMIAR"]


async def test_szczelina_z_ustawien_trafia_do_makra(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path, szczelina_mm=2.5)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    assert maszyna.historia[-1] == "PRZYGOTUJ SZCZELINA=2.5"


async def test_numery_rosna_o_jeden_i_przezywaja_restart(tmp_path):
    cykl, _ = await skalibrowany(tmp_path)
    assert cykl.opis()["nastepny_numer"] == 1
    cykl.akcja("nowy_pomiar")
    assert cykl.opis()["numer_probki"] == 1
    await poczekaj_na(cykl, "wsyp")
    assert Magazyn(tmp_path).nastepny_numer() == 2


async def test_anulowany_numer_nie_wraca_do_obiegu(tmp_path):
    cykl, _ = await skalibrowany(tmp_path)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("anuluj")
    assert cykl.opis()["ekran"] == "kalibracja"
    assert cykl.opis()["nastepny_numer"] == 2


async def test_anuluj_nie_rusza_maszyny_bez_naciśnięcia(tmp_path):
    cykl, maszyna = await skalibrowany(tmp_path)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    liczba = len(maszyna.historia)
    cykl.akcja("anuluj")
    assert len(maszyna.historia) == liczba
    assert cykl.opis()["trwa"] is False


@pytest.mark.parametrize("akcja", ["probka_wsypana", "anuluj"])
async def test_akcje_niedostepne_poza_swoim_ekranem(tmp_path, akcja):
    cykl, _ = await skalibrowany(tmp_path)
    with pytest.raises(ValueError):
        cykl.akcja(akcja)


async def test_nowy_pomiar_wymaga_kalibracji():
    cykl, _ = nowy_cykl()
    with pytest.raises(ValueError):
        cykl.akcja("nowy_pomiar")


async def test_licznik_jest_trwaly_mimo_uszkodzonego_zapisu_tymczasowego(tmp_path):
    magazyn = Magazyn(tmp_path)
    assert magazyn.pobierz_numer() == 1
    (tmp_path / "stan.json.tmp").write_text("{ uszkodzony")
    assert Magazyn(tmp_path).pobierz_numer() == 2
