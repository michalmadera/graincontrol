import json

from pomoc import poczekaj_na, skalibrowany
from stacja.kamera import BladZdjecia


async def do_zdjecia(tmp_path, blad=None):
    cykl, maszyna = await skalibrowany(tmp_path, czas_splywu_s=0)
    if blad:
        cykl.kamera.wymus_blad(blad)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("probka_wsypana")
    return cykl, maszyna


async def test_zdjecie_trafia_do_kolejki_z_kompletem_plikow(tmp_path):
    cykl, _ = await do_zdjecia(tmp_path)
    await poczekaj_na(cykl, "analiza")
    wpisy = cykl.kolejka.oczekujace()
    assert len(wpisy) == 1
    wpis = wpisy[0]
    assert wpis.png.is_file() and wpis.dng.is_file()
    pomiar = json.loads((wpis.katalog / "pomiar.json").read_text(encoding="utf-8"))
    assert pomiar["numer_probki"] == 1
    assert pomiar["id_pomiaru"] == cykl.id_pomiaru
    assert pomiar["akwizycja"]["_dummy"] is True
    assert pomiar["czas_zdjecia"]


async def test_blad_zdjecia_daje_ponowienie_bez_ruchu_maszyny(tmp_path):
    cykl, maszyna = await do_zdjecia(tmp_path, blad="Kamera nie odpowiada")
    await poczekaj_na(cykl, "blad_zdjecia")
    assert "Kamera nie odpowiada" in cykl.opis()["komunikat"]
    assert cykl.kolejka.oczekujace() == []
    historia = list(maszyna.historia)
    cykl.akcja("ponow_zdjecie")
    await poczekaj_na(cykl, "analiza")
    assert maszyna.historia == historia, "ponowienie nie może ruszać ani kalibrować maszyny"
    assert maszyna.stan().skalibrowany is True
    assert len(cykl.kolejka.oczekujace()) == 1


async def test_odrzucenie_przez_kontrakt_nie_trafia_do_kolejki(tmp_path, monkeypatch):
    cykl, _ = await skalibrowany(tmp_path, czas_splywu_s=0)

    async def odrzucone():
        return {"accepted": False, "violations": ["DigitalGain: zmierzone 1.2, profil 1.0"]}
    monkeypatch.setattr(cykl.kamera.kontroler, "shoot", odrzucone)
    cykl.akcja("nowy_pomiar")
    await poczekaj_na(cykl, "wsyp")
    cykl.akcja("probka_wsypana")
    await poczekaj_na(cykl, "blad_zdjecia")
    assert cykl.kolejka.oczekujace() == []


async def test_kamera_zglasza_odrzucenie_jako_blad(tmp_path):
    from stacja.kamera import Kamera
    kamera = Kamera(tmp_path)
    kamera.wymus_blad("awaria")
    try:
        await kamera.zrob(1)
    except BladZdjecia as exc:
        assert "awaria" in str(exc)
    else:
        raise AssertionError("oczekiwano BladZdjecia")
