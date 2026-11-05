"""Automat cyklu: jedyne miejsce, które decyduje, który ekran widzi robotnik."""
from __future__ import annotations

import asyncio
import logging
import re
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
KROKI_RUCHU = ("przygotowanie", "rozgarnianie", "czyszczenie", "kalibracja")
AKCJE_Z_DANYMI = ("nowy_pomiar", "serwis_ruch", "serwis_ustawienia", "serwis_reset_numeracji")
RUCHY_SERWISOWE = ("GORA_5MM", "DOL_5MM", "GORA_1MM", "DOL_1MM")
KOD_PARTII = re.compile(r"[A-Za-z0-9]{10}")     # BR-010
# Klipper wysyła stan co ok. 250 ms, więc flagi mogą dojść po odpowiedzi makra.
ZWLOKA_FLAG_S = 1.0
ODSTEP_PONOWIENIA_STOP_S = 1.0
KOMUNIKAT_PRZERWANIA = "Poprzednia operacja została przerwana."


_BLEDY = [
    ("odrzucono", "Tego ruchu nie można teraz wykonać."),
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
        dziennik = magazyn.cykl()
        self.numer_probki: int | None = dziennik.get("numer_probki")
        self.id_pomiaru: str | None = dziennik.get("id_pomiaru")
        self.komunikat: str | None = dziennik.get("komunikat")
        self.kod_partii: str | None = dziennik.get("kod_partii")
        self._krok = self._krok_po_restarcie(dziennik.get("krok", "gotowa"))
        self._koniec_splywu: float | None = None
        self._zadanie: asyncio.Task | None = None
        self._krok_od = float("-inf")
        self._zajety_od: float | None = None
        self._krok_przed_serwisem: str | None = None
        self._komunikat_przed_serwisem: str | None = None
        self._stop_nieudany = False
        self._ponawianie_stop: asyncio.Task | None = None

    def _krok_po_restarcie(self, krok: str) -> str:
        """Zadanie zginęło razem z procesem, więc kroku w toku nie da się po prostu wznowić."""
        if krok in KROKI_RUCHU:
            # Wyniku makra nie znamy: cykl przerwany, brudny stół wymusi czyszczenie.
            return "kalibracja"
        if krok == "splyw":
            return "wsyp"        # bez ruchu: robotnik potwierdza jeszcze raz
        if krok in ("zdjecie", "blad_zdjecia"):
            if any(w.pomiar.get("id_pomiaru") == self.id_pomiaru for w in self.kolejka.oczekujace()) \
                    or self.magazyn.wynik(self.id_pomiaru):
                return "analiza"
            self.komunikat = self.komunikat or "Zdjęcie zostało przerwane."
            return "blad_zdjecia"
        if krok == "blad":
            self.komunikat = self.komunikat or KOMUNIKAT_PRZERWANIA
        return krok

    @property
    def krok(self) -> str:
        return self._krok

    @krok.setter
    def krok(self, krok: str) -> None:
        self._krok = krok
        self._krok_od = time.monotonic()
        try:
            self.magazyn.zapisz_cykl({"krok": krok, "numer_probki": self.numer_probki,
                                      "id_pomiaru": self.id_pomiaru, "komunikat": self.komunikat,
                                      "kod_partii": self.kod_partii})
        except OSError as exc:
            # Ekran ma działać dalej; brak dziennika szkodzi dopiero przy kolejnym restarcie.
            log.error("Nie udało się zapisać dziennika cyklu: %s", exc)

    @property
    def trwa(self) -> bool:
        return self._zadanie is not None and not self._zadanie.done()

    def _ekran(self) -> str:
        stan = self.maszyna.stan()
        if not stan.polaczona:
            return "brak_polaczenia"
        if stan.webhooks in ("shutdown", "error"):
            return "zatrzymana"
        if stan.webhooks == "startup":
            return "uruchamianie"
        if stan.webhooks != "ready":
            return "brak_polaczenia"
        if self.trwa:
            self._zajety_od = None
            return self.krok
        teraz = time.monotonic()
        zwloka = ZWLOKA_FLAG_S * self.tempo
        # Makro nadal jedzie (restart stacji albo zerwane połączenie). Ma to pierwszeństwo przed
        # błędem: ODBLOKUJ nad ruszającą się maszyną skasowałoby kalibrację w środku ruchu.
        if stan.zajety and stan.w_toku:
            return "oczekiwanie"
        # Po błędzie makra blokada ma pierwszeństwo: nieudana kalibracja też zostawia skalibrowany=0.
        if self.krok == "blad" and (stan.zajety or stan.skalibrowany):
            return "blad"
        if stan.zajety:
            # Flaga mogła się jeszcze nie odświeżyć po końcu makra, więc blokada dopiero po zwłoce.
            if self._zajety_od is None:
                self._zajety_od = teraz
            return "oczekiwanie" if teraz - self._zajety_od < zwloka else "blad"
        self._zajety_od = None
        flagi_swieze = teraz - self._krok_od < zwloka
        # Kalibracja wynika ze stanu maszyny, nie z pamięci aplikacji: restart Klippera kasuje
        # skalibrowany, więc tej ścieżki nie da się ominąć.
        if self.krok == "serwis":
            return "serwis"
        if not stan.skalibrowany and not flagi_swieze:
            return "kalibracja"
        # Wsypanie ma sens tylko na wysokości załadunku; inaczej stół jest w nieznanej pozycji.
        if self.krok == "wsyp" and not stan.przygotowany and not flagi_swieze:
            return "kalibracja"
        # Nowa próbka nie może spaść na starą, niezależnie od drogi, którą tu dotarliśmy.
        if self.krok == "gotowa" and self.magazyn.brudny():
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

    def _mozna_dalej(self) -> bool:
        """Bez czekania, gdy serwera nie ma albo przed tą próbką stoją inne (nawet dziesiątki minut)."""
        if self.krok != "analiza":
            return False
        if not self.wysylka.serwer_dostepny:
            return True
        wpisy = self.kolejka.oczekujace()
        if not wpisy:
            return False
        try:
            return wpisy[0].pomiar.get("id_pomiaru") != self.id_pomiaru
        except (OSError, ValueError):
            return False

    def opis(self) -> dict:
        self._odbierz_wynik()
        ekran = self._ekran()
        pozostalo = None
        if self._koniec_splywu is not None:
            pozostalo = max(0, round((self._koniec_splywu - time.monotonic()) / self.tempo))
        return {
            "ekran": ekran,
            "trwa": self.trwa,
            "numer_probki": self.numer_probki,
            "nastepny_numer": self.magazyn.nastepny_numer(),
            "pozostalo_s": pozostalo,
            "komunikat": self.komunikat or (KOMUNIKAT_PRZERWANIA if ekran == "blad" else None),
            "wynik": self.magazyn.wynik(self.id_pomiaru) if self.krok == "wynik" else None,
            "serwer_dostepny": self.wysylka.serwer_dostepny,
            "mozna_dalej": self._mozna_dalej(),
            "stop_nieudany": self._stop_nieudany,
            "komunikat_maszyny": self.maszyna.stan().komunikat,
            "w_kolejce": len(self.kolejka.oczekujace()),
            "kolejka_pelna": self._kolejka_pelna(),
            "ostatnie_wyniki": self.magazyn.ostatnie_wyniki(),
            "skanowanie_wlaczone": self.magazyn.ustawienia["skanowanie_wlaczone"],
            "ustawienia": self.magazyn.ustawienia if ekran == "serwis" else None,
        }

    def akcja(self, nazwa: str, dane: dict | None = None) -> None:
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
            "serwis_wejdz": self._serwis_wejdz,
            "serwis_wyjdz": self._serwis_wyjdz,
            "serwis_ruch": self._serwis_ruch,
            "serwis_ustawienia": self._serwis_ustawienia,
            "serwis_reset_numeracji": self._serwis_reset_numeracji,
            "serwis_reset_odniesienia": self._serwis_reset_odniesienia,
            "porzuc_zdjecie": self._porzuc_zdjecie,
        }.get(nazwa)
        if obsluga is None:
            raise ValueError(f"Nieznana akcja: {nazwa}")
        if self._stop_nieudany:
            raise ValueError("STOP nie dotarł do maszyny")
        if self.trwa:
            raise ValueError("Maszyna pracuje")
        self._odbierz_wynik()
        if nazwa in AKCJE_Z_DANYMI:
            obsluga(dane or {})
        else:
            obsluga()

    # ------------------------------------------------------------- STOP i błędy
    async def stop(self) -> str:
        """Najpierw silniki, potem sterowanie: żaden kolejny krok cyklu nie może już ruszyć."""
        wynik = "ok"
        try:
            await self.maszyna.emergency_stop()
            self._zakoncz_ponawianie_stop()
        except (BladMakra, BrakPolaczenia, OSError, asyncio.TimeoutError) as exc:
            log.error("STOP nie dotarł do maszyny: %s", exc)
            wynik = "brak_polaczenia"
            self._stop_nieudany = True
            if self._ponawianie_stop is None or self._ponawianie_stop.done():
                self._ponawianie_stop = asyncio.create_task(self._ponawiaj_stop())
        if self.trwa:
            self._zadanie.cancel()
            await asyncio.gather(self._zadanie, return_exceptions=True)
        self._koniec_splywu = None
        # Po każdym STOP: kalibracja i czyszczenie, także gdy STOP nie dotarł i maszyna jedzie dalej.
        try:
            self.magazyn.ustaw_brudny(True)
        except OSError as exc:
            log.error("Nie udało się zapisać stanu stołu: %s", exc)
        self.komunikat = None
        self.krok = "kalibracja"
        return wynik

    def _zakoncz_ponawianie_stop(self) -> None:
        self._stop_nieudany = False
        if self._ponawianie_stop is not None and self._ponawianie_stop is not asyncio.current_task():
            self._ponawianie_stop.cancel()
        self._ponawianie_stop = None

    async def _ponawiaj_stop(self) -> None:
        """Robotnik nacisnął STOP, więc maszyna ma stanąć, gdy tylko znów będzie osiągalna."""
        while True:
            await asyncio.sleep(ODSTEP_PONOWIENIA_STOP_S * self.tempo)
            try:
                await self.maszyna.emergency_stop()
            except (BladMakra, BrakPolaczenia, OSError, asyncio.TimeoutError) as exc:
                log.warning("Ponowienie STOP: %s", exc)
                continue
            self._zakoncz_ponawianie_stop()
            return

    def _wznow(self) -> None:
        self._wymagaj("zatrzymana")
        self.komunikat = None
        self.krok = "kalibracja"
        self._uruchom(self._restartuj())

    async def _restartuj(self) -> None:
        try:
            await self.maszyna.firmware_restart()
        except (BladMakra, BrakPolaczenia, OSError) as exc:
            log.error("Restart maszyny nie powiódł się: %s", exc)

    def _przerwano(self, blad: Exception) -> None:
        log.error("Cykl przerwany na kroku %s: %s", self.krok, blad)
        self.komunikat = tekst_bledu(str(blad))
        self._koniec_splywu = None
        self.krok = "blad"

    def _odblokuj(self) -> None:
        self._wymagaj("blad")
        self._uruchom(self._po_odblokowaniu())

    async def _po_odblokowaniu(self) -> None:
        try:
            await self.maszyna.wywolaj("ODBLOKUJ")
        except (BladMakra, BrakPolaczenia) as exc:
            self._przerwano(exc)
            return
        self.komunikat = None
        self.krok = "kalibracja"

    def _wymagaj(self, ekran: str) -> None:
        if self._ekran() != ekran:
            raise ValueError(f"Akcja niedostępna na ekranie {self._ekran()}")

    def _uruchom(self, koro) -> None:
        self._zadanie = asyncio.create_task(self._strzez(koro))
        # STOP tuż po starcie anuluje zadanie, zanim coś wykona: korutyna zostaje wtedy nieużyta.
        self._zadanie.add_done_callback(lambda _: koro.close())

    async def _strzez(self, koro) -> None:
        """Nieprzewidziany błąd ma dać ekran błędu, a nie ekran „trwa” bez żadnego przycisku."""
        try:
            await koro
        except Exception as exc:
            log.exception("Nieoczekiwany błąd cyklu")
            self._przerwano(exc)

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
        self.numer_probki = None
        self.id_pomiaru = None
        self.krok = "czyszczenie"
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

    # ------------------------------------------------------------- tryb serwisowy
    def _serwis_wejdz(self) -> None:
        ekran = self._ekran()
        if ekran not in ("gotowa", "kalibracja", "oproznij", "blad_zdjecia"):
            raise ValueError("Tryb serwisowy jest niedostępny w trakcie pomiaru")
        self._krok_przed_serwisem = ekran if ekran == "blad_zdjecia" else None
        self._komunikat_przed_serwisem = self.komunikat
        self.komunikat = None
        self.krok = "serwis"

    def _serwis_wyjdz(self) -> None:
        self._wymagaj("serwis")
        if self._krok_przed_serwisem:
            self.komunikat = self._komunikat_przed_serwisem
        else:
            self.komunikat = None
        self.krok = self._krok_przed_serwisem or "gotowa"
        self._krok_przed_serwisem = None

    def _serwis_ruch(self, dane: dict) -> None:
        self._wymagaj("serwis")
        ruch = dane.get("ruch")
        if ruch not in RUCHY_SERWISOWE:
            raise ValueError(f"Nieznany ruch: {ruch}")
        self.komunikat = None
        self._krok_przed_serwisem = None    # stół się ruszył, próbka na zdjęciu nie jest już ta sama
        self._uruchom(self._wykonaj_ruch(ruch))

    async def _wykonaj_ruch(self, ruch: str) -> None:
        try:
            await self.maszyna.wywolaj(ruch)
        except (BladMakra, BrakPolaczenia) as exc:
            # Krok odrzucony nie blokuje maszyny; gdyby zablokował, _ekran pokaże ekran błędu.
            log.warning("Ruch serwisowy %s: %s", ruch, exc)
            self.komunikat = tekst_bledu(str(exc))

    def _serwis_ustawienia(self, dane: dict) -> None:
        self._wymagaj("serwis")
        self.magazyn.zmien_ustawienia(dane)

    def _serwis_reset_numeracji(self, dane: dict) -> None:
        self._wymagaj("serwis")
        if dane.get("potwierdzam") is not True:
            raise ValueError("Reset numeracji wymaga potwierdzenia")
        self.magazyn.zresetuj_numeracje()

    def _serwis_reset_odniesienia(self) -> None:
        self._wymagaj("serwis")
        self.kamera.resetuj_odniesienie()

    # ------------------------------------------------------------- pomiar
    def _kolejka_pelna(self) -> bool:
        return len(self.kolejka.oczekujace()) >= self.magazyn.ustawienia["limit_kolejki"]

    def _nowy_pomiar(self, dane: dict) -> None:
        self._wymagaj("gotowa")
        if self._kolejka_pelna():
            raise ValueError("Kolejka pełna")
        kod = dane.get("kod_partii")
        if self.magazyn.ustawienia["skanowanie_wlaczone"]:
            if not (isinstance(kod, str) and KOD_PARTII.fullmatch(kod)):
                raise ValueError("Błędny kod partii: wymagane 10 liter lub cyfr")
            self.kod_partii = kod
        else:
            self.kod_partii = None
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
        self.komunikat = None
        self.krok = "zdjecie"
        try:
            zdjecie = await self.kamera.zrob(self.numer_probki)
            self.kolejka.dodaj(zdjecie, {
                "id_pomiaru": self.id_pomiaru,
                "numer_probki": self.numer_probki,
                "kod_partii": self.kod_partii,
                "id_stacji": self.magazyn.ustawienia["id_stacji"],
                "czas_zdjecia": datetime.now(timezone.utc).isoformat(),
            })
        except BladZdjecia as exc:
            self.komunikat = str(exc)
            self.krok = "blad_zdjecia"
            return
        except OSError as exc:
            log.error("Zapis zdjęcia do kolejki: %s", exc)
            self.komunikat = "Nie udało się zapisać zdjęcia. Ponów, a jeśli się powtórzy, wezwij serwis."
            self.krok = "blad_zdjecia"
            return
        self.krok = "analiza"
        self.wysylka.obudz()

    def _ponow_zdjecie(self) -> None:
        self._wymagaj("blad_zdjecia")
        self.krok = "zdjecie"
        self._uruchom(self._zrob_zdjecie())

    def _porzuc_zdjecie(self) -> None:
        self._wymagaj("blad_zdjecia")
        self.komunikat = None
        self._zacznij_czyszczenie()

    def _dalej(self) -> None:
        self._wymagaj("wynik")
        self._zacznij_czyszczenie()

    def _dalej_bez_wyniku(self) -> None:
        self._wymagaj("analiza")
        if not self._mozna_dalej():
            raise ValueError("Serwer działa, wynik zaraz będzie")
        self._zacznij_czyszczenie()

    def _anuluj(self) -> None:
        self._wymagaj("wsyp")
        self.numer_probki = None
        self.id_pomiaru = None
        # Robotnik nacisnął „Anuluj”, a nie kalibrację: maszyna rusza dopiero po drugim przycisku.
        self.krok = "kalibracja"
