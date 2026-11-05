"""Analizator: dziś atrapa, docelowo model z repo kamyki, za tym samym interfejsem."""
from __future__ import annotations

import hashlib
from typing import Protocol


class Analizator(Protocol):
    wersja: str
    zrodlo: str

    def analizuj(self, id_pomiaru: str) -> dict: ...


class AtrapaAnalizatora:
    """Wynik powtarzalny, wyliczony z id, bez patrzenia na zdjęcie. Nie mówi nic o materiale."""

    wersja = "atrapa-1"
    zrodlo = "atrapa"
    PROG_PROC = 5.0

    def analizuj(self, id_pomiaru: str) -> dict:
        skrot = hashlib.sha256(id_pomiaru.encode()).digest()
        kamienie = 800 + int.from_bytes(skrot[:2], "big") % 1000
        wtracenia = int(kamienie * (skrot[2] % 100) / 1000)     # 0–10 %
        udzial = round(100 * wtracenia / kamienie, 2)
        return {
            "werdykt": "akceptowalna" if udzial <= self.PROG_PROC else "nieakceptowalna",
            "liczba_kamieni": kamienie,
            "liczba_wtracen": wtracenia,
            "udzial_wtracen_proc": udzial,
        }
