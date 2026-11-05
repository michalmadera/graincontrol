"""Atrapa maszyny: flagi, kolejność i czasy jak w docs/printer.cfg, bez sprzętu.

Odwzorowuje to, od czego zależy ekran: blokadę po błędzie, kasowanie kalibracji przy restarcie
i warunki wstępne makr. Nie sprawdza interlocku ruchu, bo ten pilnują makra Klippera.
"""
from __future__ import annotations

import asyncio

from .maszyna import BladMakra, BrakPolaczenia, StanMaszyny, sprawdz_makro

# Czasy z docs/architecture_baseline.md §5.4 i docs/opis_software.md §3 [s].
CZASY = {"KALIBRUJ": 105.0, "PRZYGOTUJ": 40.0, "POMIAR": 55.0}
CZAS_RUCHU_RECZNEGO = 2.0
CZAS_RESTARTU = 3.0


class SymulatorMaszyny:
    def __init__(self, tempo: float = 1.0) -> None:
        self.tempo = tempo
        self.historia: list[str] = []
        self._bledy: dict[str, str] = {}
        self._polaczona = True
        self._przerwanie: asyncio.Event | None = None
        self._przyczyna: Exception | None = None
        self._zeruj_flagi()
        self._webhooks = "ready"
        self._komunikat = ""

    def _zeruj_flagi(self) -> None:
        self._zajety = False
        self._skalibrowany = False
        self._przygotowany = False
        self._stol = None
        self._spychacz = None

    # ---------------------------------------------------------- interfejs Maszyna
    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    def stan(self) -> StanMaszyny:
        return StanMaszyny(self._polaczona, self._webhooks, self._komunikat, self._zajety,
                           self._skalibrowany, self._przygotowany, self._przerwanie is not None,
                           self._stol, self._spychacz)

    async def wywolaj(self, makro: str) -> None:
        sprawdz_makro(makro)
        if not self._polaczona:
            raise BrakPolaczenia("Brak połączenia z maszyną")
        if self._webhooks != "ready":
            raise BladMakra("Klipper nie jest gotowy")
        self.historia.append(makro)
        nazwa = makro.split()[0]

        if nazwa == "STAN_SYSTEMU":
            return
        if nazwa == "ODBLOKUJ":
            self._zajety = self._skalibrowany = self._przygotowany = False
            return
        if nazwa == "POMIAR" and not self._przygotowany:
            raise BladMakra("POMIAR: najpierw PRZYGOTUJ (stol na wysokosci zaladunku), potem wsyp probke.")
        if self._zajety:
            raise BladMakra(f"{nazwa}: system zajety (zajety=1). Jesli poprzednie makro przerwal blad - ODBLOKUJ.")
        if nazwa != "KALIBRUJ" and not self._skalibrowany:
            raise BladMakra(f"{nazwa}: osie nieskalibrowane - wykonaj KALIBRUJ.")

        self._zajety = True
        self._przygotowany = False
        if nazwa == "KALIBRUJ":
            self._skalibrowany = False
        await self._trwaj(CZASY.get(nazwa, CZAS_RUCHU_RECZNEGO), nazwa)

        if nazwa == "KALIBRUJ":
            self._skalibrowany = True
            self._stol, self._spychacz = 177.0, 0.0
        elif nazwa == "PRZYGOTUJ":
            self._przygotowany = True
            self._stol, self._spychacz = 571.5, 0.0
        elif nazwa == "POMIAR":
            self._stol, self._spychacz = 177.0, 0.0
        self._zajety = False

    async def _trwaj(self, sekundy: float, nazwa: str) -> None:
        """Błąd w trakcie zostawia zajety=1, tak jak przerwane makro w Klipperze."""
        blad = self._bledy.pop(nazwa, None)
        self._przerwanie = asyncio.Event()
        try:
            await asyncio.wait_for(self._przerwanie.wait(), sekundy * self.tempo)
        except asyncio.TimeoutError:
            pass
        else:
            raise self._przyczyna
        finally:
            self._przerwanie = None
        if blad:
            raise BladMakra(blad)

    def _przerwij(self, blad: Exception) -> None:
        if self._przerwanie is not None:
            self._przyczyna = blad
            self._przerwanie.set()

    async def emergency_stop(self) -> None:
        if not self._polaczona:
            raise BrakPolaczenia("Brak połączenia z maszyną")
        self._webhooks, self._komunikat = "shutdown", "Zatrzymanie awaryjne"
        self._przerwij(BladMakra("Klipper: zatrzymanie awaryjne"))

    async def firmware_restart(self) -> None:
        self._przerwij(BladMakra("Klipper: restart"))
        self._zeruj_flagi()
        self._webhooks, self._komunikat = "startup", "Uruchamianie"
        await asyncio.sleep(CZAS_RESTARTU * self.tempo)
        self._zeruj_flagi()
        self._webhooks, self._komunikat = "ready", ""

    # --------------------------------------------------- sterowanie testami (/api/dev)
    def wymus_blad(self, makro: str, tresc: str) -> None:
        self._bledy[makro] = tresc

    def rozlacz(self) -> None:
        self._polaczona = False
        self._przerwij(BrakPolaczenia("Utracono połączenie z maszyną"))

    def polacz(self) -> None:
        self._polaczona = True
