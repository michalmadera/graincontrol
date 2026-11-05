"""Automat cyklu: jedyne miejsce, które decyduje, który ekran widzi robotnik."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

from .kamera import BladZdjecia, Kamera
from .kolejka import Kolejka
from .magazyn import Magazyn
from .maszyna import BladMakra, BrakPolaczenia, Maszyna
from .wysylka import Wysylka


log = logging.getLogger(__name__)

SZCZELINA_CZYSZCZENIA = 0.5


_BLEDY = [
    ("INTERLOCK", "Zabezpieczenie zatrzymało ruch maszyny."),
    ("poza zakresem", "Zabezpieczenie zatrzymało ruch maszyny."),
    ("system zajety", "Maszyna jest zablokowana po poprzednim błędzie."),
    ("nieskalibrowane", "Maszyna wymaga ponownego ustawienia."),
    ("najpierw PRZYGOTUJ", "Maszyna nie była przygotowana na próbkę."),
    ("SZCZELINA", "Złe ustawienie szczeliny. Wezwij serwis."),
    ("Utracono", "Utracono połączenie z maszyną."),
]


def tekst_bledu(tresc: str) -> str:
    """Robotnik dostaje zdanie po polsku. Oryginał z Klippera (z nazwami makr) idzie do logu."""
    for fragment, tekst in _BLEDY:
        if fragment in tresc:
            return tekst
    return "Maszyna zgłosiła błąd. Jeśli się powtórzy, wezwij serwis."


class Cykl:
    def __init__(self, maszyna: Maszyna, magazyn: Magazyn, kamera: Kamera, kolejka: Kolejka,
                 wysylka: Wysylka, tempo: float = 1.0) -> None:
        self.maszyna = maszyna
        self.magazyn = magazyn
        self.kamera = kamera
        self.kolejka = kolejka
        self.wysylka = wysylka
        self.tempo = tempo
        self.krok = "gotowa"
        self.numer_probki: int | None = None
        self.id_pomiaru: str | None = None
        self.komunikat: str | None = None
        self._koniec_splywu: float | None = None
        self._zadanie: asyncio.Task | None = None

    @property
    def trwa(self) -> bool:
        return self._zadanie is not None and not self._zadanie.done()

    def _ekran(self) -> str:
        stan = self.maszyna.stan()
        if not stan.polaczona:
            return "brak_polaczenia"
        if stan.webhooks == "shutdown":
            return "zatrzymana"
        if stan.webhooks == "startup":
            return "uruchamianie"
        if stan.webhooks != "ready":
            return "brak_polaczenia"
        if self.trwa:
            return self.krok
        # Po błędzie makra blokada ma pierwszeństwo: nieudana kalibracja też zostawia skalibrowany=0.
        if self.krok == "blad" and (stan.zajety or stan.skalibrowany):
            return "blad"
        # Kalibracja wynika ze stanu maszyny, nie z pamięci aplikacji: restart Klippera kasuje
        # skalibrowany, więc tej ścieżki nie da się ominąć.
        if not stan.skalibrowany:
            return "kalibracja"
        # Licznik leży na dysku, więc blokada wraca też po restarcie stacji.
        if self.krok == "gotowa" and self._trzeba_oproznic():
            return "oproznij"
        return self.krok

    def _trzeba_oproznic(self) -> bool:
        return self.magazyn.czyszczen_od_oproznienia() >= self.magazyn.ustawienia["oproznianie_co_n"]

    def _odbierz_wynik(self) -> None:
        if self.krok == "analiza" and not self.trwa and self.magazyn.wynik(self.id_pomiaru):
            self.krok = "wynik"

    def opis(self) -> dict:
        self._odbierz_wynik()
        pozostalo = None
        if self._koniec_splywu is not None:
            pozostalo = max(0, round((self._koniec_splywu - time.monotonic()) / self.tempo))
        return {
            "ekran": self._ekran(),
            "trwa": self.trwa,
            "numer_probki": self.numer_probki,
            "nastepny_numer": self.magazyn.nastepny_numer(),
            "pozostalo_s": pozostalo,
            "komunikat": self.komunikat,
            "wynik": self.magazyn.wynik(self.id_pomiaru) if self.krok == "wynik" else None,
            "serwer_dostepny": self.wysylka.serwer_dostepny,
            "w_kolejce": len(self.kolejka.oczekujace()),
            "kolejka_pelna": self._kolejka_pelna(),
            "ostatnie_wyniki": self.magazyn.ostatnie_wyniki(),
        }

    def akcja(self, nazwa: str) -> None:
        obsluga = {
            "kalibruj": self._kalibruj,
            "nowy_pomiar": self._nowy_pomiar,
            "probka_wsypana": self._probka_wsypana,
            "anuluj": self._anuluj,
            "ponow_zdjecie": self._ponow_zdjecie,
            "dalej": self._dalej,
            "dalej_bez_wyniku": self._dalej_bez_wyniku,
            "oproznione": self._oproznione,
            "wznow": self._wznow,
            "odblokuj": self._odblokuj,
        }.get(nazwa)
        if obsluga is None:
            raise ValueError(f"Nieznana akcja: {nazwa}")
        if self.trwa:
            raise ValueError("Maszyna pracuje")
        self._odbierz_wynik()
        obsluga()

    # ------------------------------------------------------------- STOP i błędy
    async def stop(self) -> str:
        """Najpierw silniki, potem sterowanie: żaden kolejny krok cyklu nie może już ruszyć."""
        wynik = "ok"
        try:
            await self.maszyna.emergency_stop()
        except (BladMakra, BrakPolaczenia, OSError) as exc:
            log.error("STOP nie dotarł do maszyny: %s", exc)
            wynik = "brak_polaczenia"
        if self.trwa:
            self._zadanie.cancel()
            await asyncio.gather(self._zadanie, return_exceptions=True)
        self._koniec_splywu = None
        return wynik

    def _wznow(self) -> None:
        self._wymagaj("zatrzymana")
        self.krok = "kalibracja"
        self.komunikat = None
        self._uruchom(self._restartuj())

    async def _restartuj(self) -> None:
        try:
            await self.maszyna.firmware_restart()
        except (BladMakra, BrakPolaczenia, OSError) as exc:
            log.error("Restart maszyny nie powiódł się: %s", exc)

    def _przerwano(self, blad: Exception) -> None:
        log.error("Cykl przerwany na kroku %s: %s", self.krok, blad)
        self.krok = "blad"
        self.komunikat = tekst_bledu(str(blad))
        self._koniec_splywu = None

    def _odblokuj(self) -> None:
        self._wymagaj("blad")
        self._uruchom(self._po_odblokowaniu())

    async def _po_odblokowaniu(self) -> None:
        try:
            await self.maszyna.wywolaj("ODBLOKUJ")
        except (BladMakra, BrakPolaczenia) as exc:
            self._przerwano(exc)
            return
        self.krok = "kalibracja"
        self.komunikat = None

    def _wymagaj(self, ekran: str) -> None:
        if self._ekran() != ekran:
            raise ValueError(f"Akcja niedostępna na ekranie {self._ekran()}")

    def _uruchom(self, koro) -> None:
        self._zadanie = asyncio.create_task(koro)

    # ------------------------------------------------------------- kalibracja
    def _kalibruj(self) -> None:
        self._wymagaj("kalibracja")
        self.krok = "kalibracja"
        self._uruchom(self._po_kalibracji())

    async def _po_kalibracji(self) -> None:
        try:
            await self.maszyna.wywolaj("KALIBRUJ")
        except (BladMakra, BrakPolaczenia) as exc:
            self._przerwano(exc)
            return
        if self.magazyn.brudny():
            await self._czysc()
        else:
            self.krok = "gotowa"

    # ------------------------------------------------------------- czyszczenie
    def _zacznij_czyszczenie(self) -> None:
        self.numer_probki = None
        self.id_pomiaru = None
        self.krok = "czyszczenie"
        self._uruchom(self._czysc())

    async def _czysc(self) -> None:
        self.krok = "czyszczenie"
        self.numer_probki = None
        self.id_pomiaru = None
        try:
            # Wąska szczelina jawnie: przy szczelinie pomiarowej drobne kamyki zostałyby na płycie.
            await self.maszyna.wywolaj(f"PRZYGOTUJ SZCZELINA={SZCZELINA_CZYSZCZENIA}")
            await self.maszyna.wywolaj("POMIAR")
        except (BladMakra, BrakPolaczenia) as exc:
            self._przerwano(exc)
            return
        self.magazyn.po_czyszczeniu()
        self.krok = "gotowa"

    def _oproznione(self) -> None:
        self._wymagaj("oproznij")
        self.magazyn.po_oproznieniu()

    # ------------------------------------------------------------- pomiar
    def _kolejka_pelna(self) -> bool:
        return len(self.kolejka.oczekujace()) >= self.magazyn.ustawienia["limit_kolejki"]

    def _nowy_pomiar(self) -> None:
        self._wymagaj("gotowa")
        if self._kolejka_pelna():
            raise ValueError("Kolejka pełna")
        self.numer_probki = self.magazyn.pobierz_numer()
        self.id_pomiaru = str(uuid.uuid4())
        # Przed pierwszym ruchem: każde przerwanie od tej chwili wymusi czyszczenie.
        self.magazyn.ustaw_brudny(True)
        self.krok = "przygotowanie"
        self._uruchom(self._przygotuj())

    async def _przygotuj(self) -> None:
        szczelina = self.magazyn.ustawienia["szczelina_mm"]
        makro = "PRZYGOTUJ" if szczelina is None else f"PRZYGOTUJ SZCZELINA={szczelina}"
        try:
            await self.maszyna.wywolaj(makro)
        except (BladMakra, BrakPolaczenia) as exc:
            self._przerwano(exc)
            return
        self.krok = "wsyp"

    def _probka_wsypana(self) -> None:
        self._wymagaj("wsyp")
        self.krok = "splyw"
        self._uruchom(self._splyw_i_rozgarnianie())

    async def _splyw_i_rozgarnianie(self) -> None:
        czas = self.magazyn.ustawienia["czas_splywu_s"] * self.tempo
        self._koniec_splywu = time.monotonic() + czas
        await asyncio.sleep(czas)
        self._koniec_splywu = None
        self.krok = "rozgarnianie"
        try:
            await self.maszyna.wywolaj("POMIAR")
        except (BladMakra, BrakPolaczenia) as exc:
            self._przerwano(exc)
            return
        await self._zrob_zdjecie()

    async def _zrob_zdjecie(self) -> None:
        self.krok = "zdjecie"
        self.komunikat = None
        try:
            zdjecie = await self.kamera.zrob(self.numer_probki)
            self.kolejka.dodaj(zdjecie, {
                "id_pomiaru": self.id_pomiaru,
                "numer_probki": self.numer_probki,
                "id_stacji": self.magazyn.ustawienia["id_stacji"],
                "czas_zdjecia": datetime.now(timezone.utc).isoformat(),
            })
        except BladZdjecia as exc:
            self.krok = "blad_zdjecia"
            self.komunikat = str(exc)
            return
        self.krok = "analiza"
        self.wysylka.obudz()

    def _ponow_zdjecie(self) -> None:
        self._wymagaj("blad_zdjecia")
        self.krok = "zdjecie"
        self._uruchom(self._zrob_zdjecie())

    def _dalej(self) -> None:
        self._wymagaj("wynik")
        self._zacznij_czyszczenie()

    def _dalej_bez_wyniku(self) -> None:
        self._wymagaj("analiza")
        if self.wysylka.serwer_dostepny:
            raise ValueError("Serwer działa, wynik zaraz będzie")
        self._zacznij_czyszczenie()

    def _anuluj(self) -> None:
        self._wymagaj("wsyp")
        self.numer_probki = None
        self.id_pomiaru = None
        # Robotnik nacisnął „Anuluj”, a nie kalibrację: maszyna rusza dopiero po drugim przycisku.
        self.krok = "kalibracja"
