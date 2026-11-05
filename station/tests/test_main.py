import pytest
from fastapi.testclient import TestClient

from stacja.config import Konfiguracja
from stacja.main import create_app


def klient(tmp_path, maszyna):
    konf = Konfiguracja(maszyna=maszyna, tempo=0.001, dane=tmp_path, serwis="http://127.0.0.1:9",
                        moonraker="ws://127.0.0.1:9/websocket", atrapa_kamery_dozwolona=True)
    return TestClient(create_app(konf))


def test_sterowanie_dev_jest_dostepne_przy_symulatorze(tmp_path):
    with klient(tmp_path, "symulator") as k:
        assert k.get("/api/dev/historia").status_code == 200


@pytest.mark.parametrize("sciezka", ["/api/dev/reset", "/api/dev/restart", "/api/dev/rozlacz"])
def test_przy_prawdziwej_maszynie_nie_ma_sterowania_dev(tmp_path, sciezka):
    with klient(tmp_path, "moonraker") as k:
        assert k.post(sciezka).status_code in (404, 405)


def test_nieznany_rodzaj_maszyny_nie_startuje(tmp_path):
    with pytest.raises(RuntimeError):
        klient(tmp_path, "cos_innego")
