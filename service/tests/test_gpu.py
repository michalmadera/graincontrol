import sys
import types

from analiza.gpu import raport_gpu


def _torch(dostepne):
    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(is_available=lambda: dostepne, get_device_name=lambda i: "RTX testowy")
    return torch


def test_raportuje_karte_z_pytorcha(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", _torch(True))
    assert raport_gpu() == {"dostepne": True, "nazwa": "RTX testowy", "zrodlo": "torch"}


def test_brak_karty_to_informacja_a_nie_awaria(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", _torch(False))
    assert raport_gpu()["dostepne"] is False


def test_bez_pytorcha_i_bez_nvidia_smi(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)
    monkeypatch.setattr("analiza.gpu.shutil.which", lambda nazwa: None)
    assert raport_gpu() == {"dostepne": False, "nazwa": None, "zrodlo": None}
