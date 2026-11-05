import json
import uuid

import pytest
from fastapi.testclient import TestClient

from analiza.main import Konfiguracja, create_app

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


@pytest.fixture
def klient(tmp_path):
    return TestClient(create_app(Konfiguracja(dane=tmp_path, opoznienie_s=0, dev=True)))


def metadane(**zmiany):
    return {"id_pomiaru": str(uuid.uuid4()), "numer_probki": 7, "kod_partii": None,
            "id_stacji": "stacja-1", "czas_zdjecia": "2026-11-05T10:00:00+00:00",
            "akwizycja": {"ExposureTime": 82000}, **zmiany}


def wyslij(klient, dane=None, png=PNG, raw=None):
    dane = dane or metadane()
    pliki = {"zdjecie": ("zdjecie.png", png, "image/png")}
    if raw:
        pliki["raw"] = ("zdjecie.dng", raw, "application/octet-stream")
    return klient.post("/api/v1/pomiary", files=pliki, data={"metadane": json.dumps(dane)})


def test_atrapa_zwraca_wynik_oznaczony_jako_atrapa(klient):
    dane = metadane()
    odp = wyslij(klient, dane)
    assert odp.status_code == 200
    wynik = odp.json()
    assert wynik["id_pomiaru"] == dane["id_pomiaru"]
    assert wynik["zrodlo_wyniku"] == "atrapa"
    assert wynik["werdykt"] in ("akceptowalna", "nieakceptowalna")
    assert wynik["liczba_kamieni"] > 0
    assert wynik["liczba_wtracen"] <= wynik["liczba_kamieni"]
    assert wynik["udzial_wtracen_proc"] == pytest.approx(
        100 * wynik["liczba_wtracen"] / wynik["liczba_kamieni"], abs=0.01)


def test_to_samo_id_daje_ten_sam_wynik_bez_duplikatu(klient, tmp_path):
    dane = metadane()
    pierwsza = wyslij(klient, dane).json()
    druga = wyslij(klient, dane, png=PNG + b"inne").json()
    assert pierwsza == druga
    zapisane = (tmp_path / "pomiary" / dane["id_pomiaru"] / "zdjecie.png").read_bytes()
    assert zapisane == PNG


def test_zapisuje_zdjecie_raw_i_metadane(klient, tmp_path):
    dane = metadane()
    wyslij(klient, dane, raw=b"DNG")
    katalog = tmp_path / "pomiary" / dane["id_pomiaru"]
    assert (katalog / "zdjecie.dng").read_bytes() == b"DNG"
    assert json.loads((katalog / "metadane.json").read_text())["numer_probki"] == 7


def test_nie_png_jest_odrzucany(klient):
    assert wyslij(klient, png=b"GIF89a").status_code == 400


@pytest.mark.parametrize("zmiana", [
    {"id_pomiaru": "../../etc/passwd"}, {"id_pomiaru": "nie-uuid"},
    {"numer_probki": "siedem"}, {"id_stacji": ""},
])
def test_zle_metadane_sa_odrzucane_i_nic_nie_zapisuja(klient, tmp_path, zmiana):
    assert wyslij(klient, metadane(**zmiana)).status_code == 400
    assert not list((tmp_path / "pomiary").glob("*"))


def test_niekompletny_formularz_to_blad_walidacji_4xx(klient):
    odp = klient.post("/api/v1/pomiary", data={"metadane": "{}"})
    assert 400 <= odp.status_code < 500


def test_wymuszony_werdykt_i_blad(klient):
    klient.post("/api/dev/wymus", json={"werdykt": "nieakceptowalna"})
    assert wyslij(klient).json()["werdykt"] == "nieakceptowalna"
    klient.post("/api/dev/wymus", json={"status": 500})
    dane = metadane()
    assert wyslij(klient, dane).status_code == 500
    klient.post("/api/dev/wymus", json={})
    assert wyslij(klient, dane).status_code == 200, "błąd 500 nie może zablokować ponowienia"


def test_sterowanie_dev_wylaczone_domyslnie(tmp_path):
    klient = TestClient(create_app(Konfiguracja(dane=tmp_path, opoznienie_s=0)))
    assert klient.post("/api/dev/wymus", json={}).status_code == 404


def test_health_mowi_czym_jest_analizator(klient):
    odp = klient.get("/health").json()
    assert odp["status"] == "ok"
    assert odp["analizator"].startswith("atrapa")
    assert "dostepne" in odp["gpu"]
