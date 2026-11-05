"""Serwis analizy: przyjmuje zdjęcie, zwraca wynik. Reszta spec-operacyjny §5.6 jest poza zakresem etapu."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ValidationError, field_validator

from .analizator import AtrapaAnalizatora
from .gpu import raport_gpu

SYGNATURA_PNG = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class Konfiguracja:
    dane: Path
    opoznienie_s: float = 10.0
    dev: bool = False


def wczytaj() -> Konfiguracja:
    return Konfiguracja(
        dane=Path(os.environ.get("ANALIZA_DANE", "/dane")),
        opoznienie_s=float(os.environ.get("ANALIZA_OPOZNIENIE_S", "10")),
        dev=os.environ.get("ANALIZA_DEV") == "1",
    )


class Metadane(BaseModel):
    id_pomiaru: str
    numer_probki: int
    kod_partii: str | None = None
    id_stacji: str
    czas_zdjecia: str
    akwizycja: dict = {}

    @field_validator("id_pomiaru")
    @classmethod
    def _uuid(cls, wartosc: str) -> str:
        # Id staje się nazwą katalogu, więc nie może zawierać niczego poza kanonicznym UUID.
        if str(uuid.UUID(wartosc)) != wartosc:
            raise ValueError("id_pomiaru musi być UUID")
        return wartosc

    @field_validator("id_stacji")
    @classmethod
    def _niepuste(cls, wartosc: str) -> str:
        if not wartosc:
            raise ValueError("id_stacji jest wymagane")
        return wartosc


class Wymuszenie(BaseModel):
    werdykt: str | None = None
    status: int | None = None


def _utrwal(sciezka: Path) -> None:
    deskryptor = os.open(sciezka, os.O_RDONLY)
    try:
        os.fsync(deskryptor)
    finally:
        os.close(deskryptor)


def _zapisz_atomowo(cel: Path, tresc: str) -> None:
    tymczasowy = cel.with_name(cel.name + ".tmp")
    tymczasowy.write_text(tresc, encoding="utf-8")
    _utrwal(tymczasowy)
    os.replace(tymczasowy, cel)


def create_app(konfiguracja: Konfiguracja | None = None, analizator=None) -> FastAPI:
    konfiguracja = konfiguracja or wczytaj()
    pomiary = konfiguracja.dane / "pomiary"
    pomiary.mkdir(parents=True, exist_ok=True)
    analizator = analizator or AtrapaAnalizatora()
    wymuszenie = Wymuszenie()
    # Jedna analiza naraz: GPU i tak nie pomieści więcej, a ponowienie tego samego id musi poczekać.
    zamek = asyncio.Lock()
    app = FastAPI(title="GrainControl — serwis analizy")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "analizator": analizator.wersja, "gpu": raport_gpu()}

    @app.post("/api/v1/pomiary")
    async def pomiar(zdjecie: UploadFile = File(...), raw: UploadFile | None = File(None),
                     metadane: str = Form(...)) -> dict:
        try:
            dane = Metadane.model_validate(json.loads(metadane))
        except (ValidationError, json.JSONDecodeError, TypeError) as exc:
            raise HTTPException(400, f"Złe metadane: {exc}")
        if await zdjecie.read(len(SYGNATURA_PNG)) != SYGNATURA_PNG:
            raise HTTPException(400, "Zdjęcie nie jest plikiem PNG")
        await zdjecie.seek(0)

        katalog = pomiary / dane.id_pomiaru
        plik_wyniku = katalog / "wynik.json"
        async with zamek:
            if plik_wyniku.exists():
                return json.loads(plik_wyniku.read_text(encoding="utf-8"))
            if wymuszenie.status:
                raise HTTPException(wymuszenie.status, "Błąd wymuszony do testów")

            roboczy = pomiary / f".{dane.id_pomiaru}.tmp"
            shutil.rmtree(roboczy, ignore_errors=True)
            roboczy.mkdir()
            with open(roboczy / "zdjecie.png", "wb") as cel:
                shutil.copyfileobj(zdjecie.file, cel)
            _utrwal(roboczy / "zdjecie.png")
            if raw is not None:
                with open(roboczy / "zdjecie.dng", "wb") as cel:
                    shutil.copyfileobj(raw.file, cel)
                _utrwal(roboczy / "zdjecie.dng")
            _zapisz_atomowo(roboczy / "metadane.json", dane.model_dump_json(indent=1))

            await asyncio.sleep(konfiguracja.opoznienie_s)
            wynik = {
                "id_pomiaru": dane.id_pomiaru,
                **analizator.analizuj(dane.id_pomiaru),
                # Syntetyczne zdjęcie nie może dać wyniku wyglądającego na prawdziwy pomiar.
                "zrodlo_wyniku": "atrapa" if dane.akwizycja.get("_dummy") else analizator.zrodlo,
                "wersja_analizatora": analizator.wersja,
            }
            if wymuszenie.werdykt:
                wynik["werdykt"] = wymuszenie.werdykt
            _zapisz_atomowo(roboczy / "wynik.json", json.dumps(wynik, ensure_ascii=False, indent=1))
            _utrwal(roboczy)
            # Katalog pojawia się pod właściwą nazwą dopiero z kompletem plików. Stacja kasuje
            # swoją kopię zaraz po odpowiedzi, więc wszystko musi być już fizycznie na dysku.
            os.replace(roboczy, katalog)
            _utrwal(pomiary)
            return wynik

    if konfiguracja.dev:
        dev = APIRouter(prefix="/api/dev")

        @dev.post("/wymus")
        def wymus(cialo: Wymuszenie) -> dict:
            wymuszenie.werdykt, wymuszenie.status = cialo.werdykt, cialo.status
            return {"ok": True}

        app.include_router(dev)

    return app
