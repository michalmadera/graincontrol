"""Atrapa serwera Moonraker wg docs/opis_software.md §2, także jako osobny proces do Playwrighta.

Mówi protokołem JSON-RPC przez WebSocket i prowadzi flagi jak printer.cfg, ale nie jest dowodem,
że prawdziwy Moonraker zachowuje się tak samo.
"""
from __future__ import annotations

import asyncio
import json
import sys

from websockets.asyncio.server import serve


class AtrapaMoonrakera:
    def __init__(self, czas_makra: float = 0.02) -> None:
        self.czas_makra = czas_makra
        self.skrypty: list[str] = []
        self.bledy: dict[str, str] = {}
        self.stan = {"zajety": 0, "skalibrowany": 0, "przygotowany": 0}
        self.webhooks = {"state": "ready", "state_message": ""}
        self.idle = "Ready"
        self.klienci = set()
        self.polaczenia = 0
        self._serwer = None
        self.port = None

    async def start(self, port: int = 0) -> None:
        self._serwer = await serve(self._obsluz, "127.0.0.1", port)
        self.port = self._serwer.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        self._serwer.close()
        for klient in list(self.klienci):
            await klient.close()
        await self._serwer.wait_closed()

    @property
    def adres(self) -> str:
        return f"ws://127.0.0.1:{self.port}/websocket"

    def _obiekty(self) -> dict:
        return {"gcode_macro STAN_SYSTEMU": dict(self.stan), "webhooks": dict(self.webhooks),
                "idle_timeout": {"state": self.idle}}

    async def rozeslij(self, metoda: str, parametry=None) -> None:
        tresc = {"jsonrpc": "2.0", "method": metoda}
        if parametry is not None:
            tresc["params"] = parametry
        for klient in list(self.klienci):
            await klient.send(json.dumps(tresc))

    async def _zmiana(self) -> None:
        await self.rozeslij("notify_status_update", [self._obiekty(), 1.0])

    async def _obsluz(self, klient) -> None:
        self.klienci.add(klient)
        self.polaczenia += 1
        try:
            async for tresc in klient:
                # Makro trwa minuty; odczyt musi iść dalej, żeby STOP dotarł w trakcie.
                asyncio.ensure_future(self._zadanie(klient, json.loads(tresc)))
        finally:
            self.klienci.discard(klient)

    async def _zadanie(self, klient, zadanie: dict) -> None:
        metoda, ident = zadanie["method"], zadanie.get("id")
        wynik, blad = "ok", None
        if metoda == "printer.objects.subscribe":
            if self.webhooks["state"] == "startup":
                blad = {"code": 503, "message": "Klippy Host not connected"}
            else:
                wynik = {"status": self._obiekty(), "eventtime": 1.0}
        elif metoda == "printer.gcode.script":
            blad = await self._skrypt(zadanie["params"]["script"])
        elif metoda == "printer.emergency_stop":
            self.webhooks = {"state": "shutdown", "state_message": "Emergency stop"}
            await self.rozeslij("notify_klippy_shutdown")
            await self._zmiana()
        elif metoda == "printer.firmware_restart":
            asyncio.ensure_future(self._restart())
        else:
            blad = {"code": 404, "message": f"Nieznana metoda {metoda}"}
        odpowiedz = {"jsonrpc": "2.0", "id": ident}
        odpowiedz.update({"error": blad} if blad else {"result": wynik})
        await klient.send(json.dumps(odpowiedz))

    async def _skrypt(self, skrypt: str) -> dict | None:
        self.skrypty.append(skrypt)
        nazwa = skrypt.split()[0]
        if nazwa == "ODBLOKUJ":
            self.stan.update(zajety=0, skalibrowany=0, przygotowany=0)
            await self._zmiana()
            return None
        if nazwa == "POMIAR" and not self.stan["przygotowany"]:
            return {"code": 400, "message": "POMIAR: najpierw PRZYGOTUJ"}
        if self.stan["zajety"]:
            return {"code": 400, "message": f"{nazwa}: system zajety (zajety=1)."}
        if nazwa != "KALIBRUJ" and not self.stan["skalibrowany"]:
            return {"code": 400, "message": f"{nazwa}: osie nieskalibrowane - wykonaj KALIBRUJ."}

        self.stan.update(zajety=1, przygotowany=0)
        self.idle = "Printing"
        await self._zmiana()
        await asyncio.sleep(self.czas_makra)
        if self.webhooks["state"] != "ready":
            return {"code": 400, "message": "Klipper: shutdown"}
        self.idle = "Ready"
        tresc = self.bledy.pop(nazwa, None)
        if tresc:
            await self._zmiana()
            return {"code": 400, "message": tresc}
        self.stan["zajety"] = 0
        if nazwa == "KALIBRUJ":
            self.stan["skalibrowany"] = 1
        if nazwa == "PRZYGOTUJ":
            self.stan["przygotowany"] = 1
        await self._zmiana()
        return None

    async def _restart(self) -> None:
        self.webhooks = {"state": "startup", "state_message": "Startup"}
        self.stan.update(zajety=0, skalibrowany=0, przygotowany=0)
        await self.rozeslij("notify_klippy_disconnected")
        await asyncio.sleep(self.czas_makra)
        self.webhooks = {"state": "ready", "state_message": ""}
        await self.rozeslij("notify_klippy_ready")


async def _glowna(port: int) -> None:
    atrapa = AtrapaMoonrakera(czas_makra=0.5)
    await atrapa.start(port)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(_glowna(int(sys.argv[1])))
