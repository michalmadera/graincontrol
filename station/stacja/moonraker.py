"""Klient Moonrakera wg docs/opis_software.md §2: JSON-RPC 2.0 przez WebSocket.

Zgodność z prawdziwym Moonrakerem nie jest jeszcze sprawdzona: testy idą na atrapie.
"""
from __future__ import annotations

import asyncio
import itertools
import json
import logging

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from .maszyna import BladMakra, BrakPolaczenia, StanMaszyny, sprawdz_makro

log = logging.getLogger(__name__)

OBIEKTY = {
    "gcode_macro STAN_SYSTEMU": ["zajety", "skalibrowany", "przygotowany"],
    "webhooks": ["state", "state_message"],
    # „Printing” odróżnia działające makro od blokady po błędzie (zajety=1 w obu przypadkach).
    "idle_timeout": ["state"],
    "manual_stepper stol": ["position"],
    "manual_stepper spychacz": ["position"],
}
LIMIT_ZLECENIA_S = 5.0


class MoonrakerMaszyna:
    def __init__(self, adres: str, odstep_ponowien: float = 2.0) -> None:
        self.adres = adres
        self.odstep_ponowien = odstep_ponowien
        self._polaczenie = None
        self._gotowe = False
        self._obiekty: dict[str, dict] = {}
        self._oczekujace: dict[int, asyncio.Future] = {}
        self._numery = itertools.count(1)
        self._zadanie: asyncio.Task | None = None
        self._subskrypcja: asyncio.Task | None = None

    async def start(self) -> None:
        self._zadanie = asyncio.create_task(self._petla())

    async def stop(self) -> None:
        if self._zadanie:
            self._zadanie.cancel()
            await asyncio.gather(self._zadanie, return_exceptions=True)
            self._zadanie = None

    # ------------------------------------------------------------- stan
    def stan(self) -> StanMaszyny:
        makro = self._obiekty.get("gcode_macro STAN_SYSTEMU", {})
        webhooks = self._obiekty.get("webhooks", {})
        return StanMaszyny(
            polaczona=self._polaczenie is not None and self._gotowe,
            webhooks=webhooks.get("state", "startup"),
            komunikat=webhooks.get("state_message", ""),
            zajety=bool(makro.get("zajety", 0)),
            skalibrowany=bool(makro.get("skalibrowany", 0)),
            przygotowany=bool(makro.get("przygotowany", 0)),
            w_toku=self._obiekty.get("idle_timeout", {}).get("state") == "Printing",
            stol=self._obiekty.get("manual_stepper stol", {}).get("position"),
            spychacz=self._obiekty.get("manual_stepper spychacz", {}).get("position"),
        )

    # ------------------------------------------------------------- polecenia
    async def wywolaj(self, makro: str) -> None:
        sprawdz_makro(makro)
        # Bez limitu czasu: odpowiedź przychodzi dopiero po końcu makra, nawet po minutach.
        await self._zlec("printer.gcode.script", {"script": makro})

    async def emergency_stop(self) -> None:
        await asyncio.wait_for(self._zlec("printer.emergency_stop"), LIMIT_ZLECENIA_S)

    async def firmware_restart(self) -> None:
        await asyncio.wait_for(self._zlec("printer.firmware_restart"), LIMIT_ZLECENIA_S)

    async def _zlec(self, metoda: str, parametry: dict | None = None):
        polaczenie = self._polaczenie
        if polaczenie is None:
            raise BrakPolaczenia("Brak połączenia z maszyną")
        numer = next(self._numery)
        odpowiedz = asyncio.get_running_loop().create_future()
        self._oczekujace[numer] = odpowiedz
        tresc = {"jsonrpc": "2.0", "method": metoda, "id": numer}
        if parametry:
            tresc["params"] = parametry
        try:
            await polaczenie.send(json.dumps(tresc))
            return await odpowiedz
        except WebSocketException as exc:
            raise BrakPolaczenia("Utracono połączenie z maszyną") from exc
        finally:
            self._oczekujace.pop(numer, None)

    # ------------------------------------------------------------- połączenie
    async def _petla(self) -> None:
        while True:
            try:
                async with connect(self.adres, max_size=None) as polaczenie:
                    self._polaczenie = polaczenie
                    self._zacznij_subskrypcje()
                    try:
                        async for tresc in polaczenie:
                            self._odbierz(json.loads(tresc))
                    finally:
                        if self._subskrypcja:
                            self._subskrypcja.cancel()
            except (OSError, WebSocketException, asyncio.TimeoutError) as exc:
                log.warning("Połączenie z Moonrakerem: %s", exc)
            finally:
                self._rozlaczono()
            await asyncio.sleep(self.odstep_ponowien)

    def _rozlaczono(self) -> None:
        self._polaczenie = None
        self._gotowe = False
        for odpowiedz in self._oczekujace.values():
            if not odpowiedz.done():
                odpowiedz.set_exception(BrakPolaczenia("Utracono połączenie z maszyną"))

    def _zacznij_subskrypcje(self) -> None:
        if self._subskrypcja:
            self._subskrypcja.cancel()
        self._subskrypcja = asyncio.create_task(self._subskrybuj())

    async def _subskrybuj(self) -> None:
        """Klipper może jeszcze startować: ponawiamy, aż Moonraker poda stan inny niż „startup”.

        Nie czekamy na notify_klippy_ready, bo nieudany start kończy się stanem „error” bez tego
        powiadomienia i ekran zostałby na zawsze na „Maszyna się uruchamia”.
        """
        while True:
            try:
                wynik = await self._zlec("printer.objects.subscribe", {"objects": OBIEKTY})
            except (BladMakra, BrakPolaczenia) as exc:
                log.info("Subskrypcja jeszcze niemożliwa: %s", exc)
                self._obiekty["webhooks"] = {"state": "startup", "state_message": str(exc)}
                self._gotowe = True
                await asyncio.sleep(self.odstep_ponowien)
                continue
            self._obiekty = dict(wynik["status"])
            self._gotowe = True
            if self._obiekty.get("webhooks", {}).get("state") != "startup":
                return
            await asyncio.sleep(self.odstep_ponowien)

    def _odbierz(self, tresc: dict) -> None:
        metoda = tresc.get("method")
        if metoda is None:
            odpowiedz = self._oczekujace.get(tresc.get("id"))
            if odpowiedz is None or odpowiedz.done():
                return
            if "error" in tresc:
                odpowiedz.set_exception(BladMakra(tresc["error"].get("message", "Błąd Klippera")))
            else:
                odpowiedz.set_result(tresc.get("result"))
        elif metoda == "notify_status_update":
            for nazwa, zmiany in tresc["params"][0].items():
                self._obiekty.setdefault(nazwa, {}).update(zmiany)
        elif metoda == "notify_klippy_ready":
            self._zacznij_subskrypcje()
        elif metoda == "notify_klippy_shutdown":
            self._obiekty.setdefault("webhooks", {})["state"] = "shutdown"
        elif metoda == "notify_klippy_disconnected":
            # Restart Klippera kasuje flagi; stare „skalibrowany” nie może przetrwać do ponownej subskrypcji.
            self._obiekty = {"webhooks": {"state": "startup", "state_message": "Klipper niedostępny"}}
            self._zacznij_subskrypcje()
