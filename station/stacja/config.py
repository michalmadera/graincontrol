"""Konfiguracja stacji ze zmiennych środowiskowych."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DOMYSLNE_DANE = Path(__file__).resolve().parents[1] / "data"


@dataclass(frozen=True)
class Konfiguracja:
    maszyna: str
    tempo: float
    dane: Path
    serwis: str
    moonraker: str = "ws://127.0.0.1:7125/websocket"
    atrapa_kamery_dozwolona: bool = False

    @property
    def symulator(self) -> bool:
        return self.maszyna == "symulator"


def wczytaj() -> Konfiguracja:
    return Konfiguracja(
        maszyna=os.environ.get("STACJA_MASZYNA", "moonraker"),
        tempo=float(os.environ.get("STACJA_TEMPO", "1")),
        dane=Path(os.environ.get("STACJA_DANE", DOMYSLNE_DANE)).expanduser(),
        serwis=os.environ.get("STACJA_SERWIS", "http://127.0.0.1:8000"),
        moonraker=os.environ.get("STACJA_MOONRAKER", "ws://127.0.0.1:7125/websocket"),
        atrapa_kamery_dozwolona=os.environ.get("STACJA_ATRAPA_KAMERY") == "1",
    )
