"""Trwały stan stacji. Musi przeżyć restart i zanik prądu, więc zapis jest atomowy."""
from __future__ import annotations

import json
import os
from pathlib import Path

LIMIT_WYNIKOW = 200      # więcej niż mieści kolejka, żeby wyniki po przerwie nie przepadały

USTAWIENIA_DOMYSLNE = {
    "skanowanie_wlaczone": False,
    "czas_splywu_s": 30,
    "szczelina_mm": None,       # None: PRZYGOTUJ bez parametru (wartość z printer.cfg)
    "limit_kolejki": 50,
    "oproznianie_co_n": 1,
    "id_stacji": "stacja-1",
    "adres_serwisu": None,      # None: adres z konfiguracji startowej
}


def _liczba(wartosc) -> bool:
    return isinstance(wartosc, (int, float)) and not isinstance(wartosc, bool)


def _calkowita(wartosc) -> bool:
    return isinstance(wartosc, int) and not isinstance(wartosc, bool)


_WALIDACJA = {
    "skanowanie_wlaczone": lambda w: isinstance(w, bool),
    "czas_splywu_s": lambda w: _liczba(w) and w >= 0,
    # 0,5 mm to minimum z printer.cfg (szczelina_min).
    "szczelina_mm": lambda w: w is None or (_liczba(w) and w >= 0.5),
    "limit_kolejki": lambda w: _calkowita(w) and w >= 1,
    "oproznianie_co_n": lambda w: _calkowita(w) and w >= 1,
    "id_stacji": lambda w: isinstance(w, str) and bool(w),
    "adres_serwisu": lambda w: w is None or (isinstance(w, str) and w.startswith(("http://", "https://"))),
}


class Magazyn:
    def __init__(self, katalog: Path) -> None:
        self.katalog = Path(katalog)
        self.katalog.mkdir(parents=True, exist_ok=True)
        self._plik = self.katalog / "stan.json"
        self._dane = self._wczytaj()

    def _wczytaj(self) -> dict:
        try:
            return json.loads(self._plik.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"nastepny_numer": 1, "ustawienia": {}}

    def zapisz(self) -> None:
        tymczasowy = self._plik.with_name(self._plik.name + ".tmp")
        with open(tymczasowy, "w", encoding="utf-8") as plik:
            json.dump(self._dane, plik, ensure_ascii=False, indent=1)
            plik.flush()
            os.fsync(plik.fileno())
        os.replace(tymczasowy, self._plik)

    # ------------------------------------------------------------- numeracja
    def nastepny_numer(self) -> int:
        return self._dane["nastepny_numer"]

    def pobierz_numer(self) -> int:
        """Numer zużywa się przy pobraniu, więc anulowana próbka nie zwalnia go ponownie."""
        numer = self._dane["nastepny_numer"]
        self._dane["nastepny_numer"] = numer + 1
        self.zapisz()
        return numer

    def zresetuj_numeracje(self) -> None:
        self._dane["nastepny_numer"] = 1
        self.zapisz()

    # ------------------------------------------------------------- dziennik cyklu
    def cykl(self) -> dict:
        return self._dane.get("cykl", {})

    def zapisz_cykl(self, dziennik: dict) -> None:
        if self._dane.get("cykl") != dziennik:
            self._dane["cykl"] = dziennik
            self.zapisz()

    # ------------------------------------------------------------- stół i pudełko
    def brudny(self) -> bool:
        return self._dane.get("brudny", False)

    def ustaw_brudny(self, brudny: bool) -> None:
        self._dane["brudny"] = brudny
        self.zapisz()

    def czyszczen_od_oproznienia(self) -> int:
        return self._dane.get("czyszczen", 0)

    def po_czyszczeniu(self) -> None:
        self._dane["brudny"] = False
        self._dane["czyszczen"] = self.czyszczen_od_oproznienia() + 1
        self.zapisz()

    def po_oproznieniu(self) -> None:
        self._dane["czyszczen"] = 0
        self.zapisz()

    # ------------------------------------------------------------- wyniki
    def zapisz_wynik(self, wynik: dict) -> None:
        wyniki = self._dane.setdefault("wyniki", [])
        # Awaria między zapisem wyniku a usunięciem zdjęcia kończy się ponowną wysyłką tego samego id.
        wyniki[:] = [w for w in wyniki if w.get("id_pomiaru") != wynik.get("id_pomiaru")]
        wyniki.append(wynik)
        del wyniki[:-LIMIT_WYNIKOW]
        self.zapisz()

    def wynik(self, id_pomiaru: str | None) -> dict | None:
        return next((w for w in self._dane.get("wyniki", []) if w.get("id_pomiaru") == id_pomiaru), None)

    def ostatnie_wyniki(self, ile: int = 5) -> list[dict]:
        return list(reversed(self._dane.get("wyniki", [])[-ile:]))

    # ------------------------------------------------------------- ustawienia
    @property
    def ustawienia(self) -> dict:
        return {**USTAWIENIA_DOMYSLNE, **self._dane["ustawienia"]}

    def zmien_ustawienia(self, zmiany: dict) -> None:
        for nazwa, wartosc in zmiany.items():
            sprawdz = _WALIDACJA.get(nazwa)
            if sprawdz is None:
                raise ValueError(f"Nieznane ustawienie: {nazwa}")
            if not sprawdz(wartosc):
                raise ValueError(f"Zła wartość ustawienia {nazwa}: {wartosc!r}")
        self._dane["ustawienia"].update(zmiany)
        self.zapisz()
