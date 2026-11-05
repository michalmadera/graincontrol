"""Wysyłka pomiarów na serwer: kolejność FIFO, plik znika dopiero po zapisaniu wyniku."""
from __future__ import annotations

import asyncio
import json
import logging

import httpx

from .kolejka import Kolejka, Wpis
from .magazyn import Magazyn

LIMIT_CZASU_S = 60.0
ODSTEP_PONOWIEN_S = 5.0
WERDYKTY = ("akceptowalna", "nieakceptowalna")

log = logging.getLogger(__name__)


class BladSerwera(RuntimeError):
    """Serwer odpowiada, ale nie dał wyniku. Traktowane jak niedostępny; zdjęcie zostaje."""


class Wysylka:
    def __init__(self, kolejka: Kolejka, magazyn: Magazyn, adres: str,
                 transport: httpx.AsyncBaseTransport | None = None, tempo: float = 1.0) -> None:
        self.kolejka = kolejka
        self.magazyn = magazyn
        self.adres = adres
        self.tempo = tempo
        self._transport = transport
        self.serwer_dostepny = True
        self._nowe = asyncio.Event()
        self._zadanie: asyncio.Task | None = None

    def start(self) -> None:
        self._zadanie = asyncio.create_task(self._petla())

    async def stop(self) -> None:
        if self._zadanie:
            self._zadanie.cancel()
            await asyncio.gather(self._zadanie, return_exceptions=True)
            self._zadanie = None

    def obudz(self) -> None:
        self._nowe.set()

    async def _petla(self) -> None:
        async with httpx.AsyncClient(transport=self._transport, timeout=LIMIT_CZASU_S) as klient:
            while True:
                self._nowe.clear()
                wpisy = self.kolejka.oczekujace()
                if not wpisy:
                    await self._nowe.wait()
                    continue
                try:
                    await self._wyslij(klient, wpisy[0])
                    self.serwer_dostepny = True
                except (httpx.TransportError, BladSerwera) as exc:
                    # Serwer wróci, zdjęcie czeka. Kolejność FIFO zostaje zachowana.
                    log.warning("Wysyłka: %s", exc)
                    self.serwer_dostepny = False
                    await asyncio.sleep(ODSTEP_PONOWIEN_S * self.tempo)
                except Exception:
                    # Pętla nie może zginąć po cichu, bo wtedy nic się już nie wyśle.
                    log.exception("Nieoczekiwany błąd wysyłki")
                    self.serwer_dostepny = False
                    await asyncio.sleep(ODSTEP_PONOWIEN_S * self.tempo)

    def _adres(self) -> str:
        return self.magazyn.ustawienia["adres_serwisu"] or self.adres

    async def _wyslij(self, klient: httpx.AsyncClient, wpis: Wpis) -> None:
        try:
            pomiar = wpis.pomiar
            pliki = {"zdjecie": ("zdjecie.png", wpis.png.read_bytes(), "image/png")}
            if wpis.dng:
                pliki["raw"] = ("zdjecie.dng", wpis.dng.read_bytes(), "application/octet-stream")
            dane = {"metadane": json.dumps(pomiar, ensure_ascii=False)}
        except (OSError, ValueError) as exc:
            # Wpisu nie da się już wysłać; nie może zablokować próbek stojących za nim.
            # Wynik z błędem kończy też ekran analizy, jeśli to bieżąca próbka.
            log.error("Uszkodzony wpis kolejki %s: %s", wpis.katalog.name, exc)
            self.magazyn.zapisz_wynik({
                "id_pomiaru": wpis.katalog.name.split("_", 1)[-1], "numer_probki": None,
                "blad": "Uszkodzony zapis zdjęcia na stacji",
            })
            self.kolejka.odrzuc(wpis)
            return

        odpowiedz = await klient.post(f"{self._adres()}/api/v1/pomiary", files=pliki, data=dane)
        # Tylko 400 i 422 mówią o samym zdjęciu. Pozostałe kody (zły adres, proxy, przeciążenie)
        # nie mogą opróżnić kolejki do katalogu odrzuconych.
        if odpowiedz.status_code in (400, 422):
            self.magazyn.zapisz_wynik({
                "id_pomiaru": pomiar["id_pomiaru"], "numer_probki": pomiar["numer_probki"],
                "blad": self._tresc_bledu(odpowiedz),
            })
            self.kolejka.odrzuc(wpis)
            return
        if not odpowiedz.is_success:
            raise BladSerwera(f"kod {odpowiedz.status_code}")
        wynik = self._sprawdz_wynik(odpowiedz, pomiar["id_pomiaru"])
        # Wynik na dysku przed usunięciem zdjęcia; awaria pomiędzy kończy się tylko
        # ponowną wysyłką, którą serwer rozpoznaje po id.
        self.magazyn.zapisz_wynik({**wynik, "numer_probki": pomiar["numer_probki"]})
        self.kolejka.usun(wpis)

    @staticmethod
    def _sprawdz_wynik(odpowiedz: httpx.Response, id_pomiaru: str) -> dict:
        """Zdjęcie kasujemy tylko po wyniku na pewno dla tego pomiaru, nie po dowolnym 200."""
        try:
            wynik = odpowiedz.json()
        except ValueError as exc:
            raise BladSerwera("odpowiedź nie jest JSON-em") from exc
        if not isinstance(wynik, dict) or wynik.get("id_pomiaru") != id_pomiaru \
                or wynik.get("werdykt") not in WERDYKTY or not isinstance(wynik.get("zrodlo_wyniku"), str):
            raise BladSerwera("odpowiedź nie jest wynikiem tego pomiaru")
        return wynik

    @staticmethod
    def _tresc_bledu(odpowiedz: httpx.Response) -> str:
        try:
            return str(odpowiedz.json()["detail"])
        except (ValueError, KeyError, TypeError):
            return f"Serwer odrzucił zdjęcie (kod {odpowiedz.status_code})"
