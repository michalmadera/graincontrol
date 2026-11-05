"""Interfejs maszyny. Ekran i cykl nie wiedzą, czy po drugiej stronie jest Klipper, czy symulator."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


class MakroNiedozwolone(ValueError):
    """Komenda spoza listy z docs/opis_software.md §3. Nie może dotrzeć do Moonrakera."""


class BladMakra(RuntimeError):
    """Makro odrzucone lub przerwane. Treść pochodzi z Klippera."""


class BrakPolaczenia(RuntimeError):
    """Maszyna niedostępna, wynik makra nieznany."""


# `fullmatch`, żeby druga linia ani parametr nie przemyciły komendy omijającej interlock.
_MAKRA = re.compile(
    r"KALIBRUJ|POMIAR|STAN_SYSTEMU|ODBLOKUJ"
    r"|PRZYGOTUJ(?: SZCZELINA=\d+(?:\.\d+)?)?"
    r"|(?:GORA|DOL)_(?:5|1)MM"
)


def sprawdz_makro(makro: str) -> str:
    if not _MAKRA.fullmatch(makro):
        raise MakroNiedozwolone(f"Makro spoza listy: {makro!r}")
    return makro


@dataclass(frozen=True)
class StanMaszyny:
    polaczona: bool
    webhooks: str               # ready / startup / shutdown / error
    komunikat: str
    zajety: bool
    skalibrowany: bool
    przygotowany: bool
    w_toku: bool = False        # makro faktycznie się wykonuje (odróżnia pracę od blokady po błędzie)
    stol: float | None = None
    spychacz: float | None = None


class Maszyna(Protocol):
    def stan(self) -> StanMaszyny: ...

    async def wywolaj(self, makro: str) -> None:
        """Czeka na koniec makra (także minuty). Błąd to BladMakra lub BrakPolaczenia."""

    async def emergency_stop(self) -> None: ...

    async def firmware_restart(self) -> None: ...
