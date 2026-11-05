"""Backend ekranu stacji: stan dla UI, akcje robotnika, sterowanie atrapą w testach."""
from __future__ import annotations

import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import Konfiguracja, wczytaj
from .cykl import Cykl
from .kamera import Kamera
from .kolejka import Kolejka
from .magazyn import Magazyn
from .symulator import SymulatorMaszyny
from .wysylka import Wysylka

STATIC = Path(__file__).resolve().parent / "static"


class Blad(BaseModel):
    makro: str
    tresc: str


def zbuduj(app: FastAPI, konfiguracja: Konfiguracja) -> None:
    if not konfiguracja.symulator:
        raise RuntimeError(f"Nieznana maszyna: {konfiguracja.maszyna}")
    app.state.maszyna = SymulatorMaszyny(konfiguracja.tempo)
    dane = konfiguracja.dane
    magazyn, kolejka = Magazyn(dane), Kolejka(dane)
    app.state.wysylka = Wysylka(kolejka, magazyn, konfiguracja.serwis, tempo=konfiguracja.tempo)
    app.state.cykl = Cykl(app.state.maszyna, magazyn, Kamera(dane), kolejka, app.state.wysylka,
                          konfiguracja.tempo)


def router_dev(app: FastAPI, konfiguracja: Konfiguracja) -> APIRouter:
    """Sterowanie symulatorem. Montowane wyłącznie przy symulatorze, nigdy przy maszynie."""
    dev = APIRouter(prefix="/api/dev")

    @dev.post("/reset")
    async def reset() -> dict:
        await app.state.wysylka.stop()
        shutil.rmtree(konfiguracja.dane, ignore_errors=True)
        zbuduj(app, konfiguracja)
        app.state.wysylka.start()
        return {"ok": True}

    @dev.post("/rozlacz")
    def rozlacz() -> dict:
        app.state.maszyna.rozlacz()
        return {"ok": True}

    @dev.post("/polacz")
    def polacz() -> dict:
        app.state.maszyna.polacz()
        return {"ok": True}

    @dev.post("/restart")
    async def restart() -> dict:
        await app.state.maszyna.firmware_restart()
        return {"ok": True}

    @dev.post("/blad")
    def blad(cialo: Blad) -> dict:
        app.state.maszyna.wymus_blad(cialo.makro, cialo.tresc)
        return {"ok": True}

    @dev.post("/ustawienia")
    def ustawienia(zmiany: dict) -> dict:
        app.state.cykl.magazyn.zmien_ustawienia(zmiany)
        return app.state.cykl.magazyn.ustawienia

    @dev.post("/serwis")
    def serwis(zmiana: dict) -> dict:
        app.state.wysylka.adres = zmiana["adres"]
        return {"ok": True}

    @dev.post("/blad-zdjecia")
    def blad_zdjecia(cialo: Blad) -> dict:
        app.state.cykl.kamera.wymus_blad(cialo.tresc)
        return {"ok": True}

    @dev.get("/historia")
    def historia() -> list[str]:
        return app.state.maszyna.historia

    return dev


def create_app(konfiguracja: Konfiguracja | None = None) -> FastAPI:
    konfiguracja = konfiguracja or wczytaj()

    @asynccontextmanager
    async def cykl_zycia(app: FastAPI):
        app.state.wysylka.start()
        yield
        await app.state.wysylka.stop()

    app = FastAPI(title="GrainControl — stacja", lifespan=cykl_zycia)
    zbuduj(app, konfiguracja)
    if konfiguracja.symulator:
        app.include_router(router_dev(app, konfiguracja))

    @app.get("/api/stan")
    def stan() -> dict:
        return app.state.cykl.opis()

    @app.post("/api/akcja/{nazwa}")
    async def akcja(nazwa: str) -> dict:
        try:
            app.state.cykl.akcja(nazwa)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        return app.state.cykl.opis()

    if STATIC.exists():
        app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(STATIC / "index.html")

    return app


app = create_app()
