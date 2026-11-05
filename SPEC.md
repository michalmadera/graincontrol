# Spec: UI stanowiska „Kostka mati”

Pełne uzasadnienia i szczegóły przebiegu:
[docs/superpowers/specs/2026-11-05-ui-stanowiska-design.md](docs/superpowers/specs/2026-11-05-ui-stanowiska-design.md)
(dalej: **Projekt**). Interfejs maszyny: [docs/opis_software.md](docs/opis_software.md).

## Objective

Robotnik bez wiedzy technicznej wykonuje pomiar próbki na ekranie dotykowym 1280 × 800 przy
maszynie, prowadzony krok po kroku. Maszyna rozgarnia próbkę, robi zdjęcie, wysyła je na serwer
z GPU, a robotnik czeka na wynik.

Na tym etapie cały przebieg ma działać i być testowalny **na atrapach**: maszyny, kamery i analizy.
Sprzęt i model podłącza się później zmianą konfiguracji, bez przebudowy ekranu.

## Tech Stack

- **Stacja (Pi, bez Dockera):** Python 3.11+, FastAPI, uvicorn, `websockets`, `httpx`; UI: React 18 + Vite 5,
  budowane do statycznych plików serwowanych przez FastAPI, jak `acquisition/`.
- **Zdjęcia:** `CaptureController` z `acquisition/server/`, bez drugiej implementacji.
- **Serwis (Docker):** Python 3.11, FastAPI. Warianty obrazu: `mock` i `gpu` (PyTorch + CUDA).
- **Testy:** pytest, `@playwright/test` (Chromium, widok 1280 × 800).

## Commands

```bash
# Instalacja (raz)
python3 -m venv .venv && .venv/bin/pip install -r station/requirements-dev.txt -r service/requirements.txt
npm --prefix station/web ci

# Uruchomienie całości na atrapach, UI na http://127.0.0.1:8100
station/run-dev.sh

# Testy
.venv/bin/python -m pytest station/tests service/tests -q
npm --prefix station/web run test:e2e

# Budowa UI (wynik: station/stacja/static, commitowany, bo Pi nie ma Node)
npm --prefix station/web run build

# Serwis w Dockerze
docker compose -f service/docker-compose.yml --profile mock up --build
docker compose -f service/docker-compose.yml --profile gpu up --build
```

## Project Structure

```
station/
  stacja/          backend: config, store, machine_*, cycle, camera, uploader, main
  stacja/static/   zbudowane UI
  tests/           pytest
  web/src/         React: App, ekrany, api
  web/e2e/         Playwright
  run-dev.sh       stacja + serwis na atrapach
service/
  analiza/         FastAPI: main, analyzer, store
  tests/           pytest
  Dockerfile       warianty mock i gpu
  docker-compose.yml
```

`acquisition/` pozostaje bez zmian funkcjonalnych.

## Code Style

Kod i komentarze po polsku tam, gdzie opisują domenę, jak w `acquisition/`. Komentarze wyjaśniają
„dlaczego”. Typy w Pythonie, funkcje i moduły małe, atrapy za tym samym interfejsem co prawdziwe.

```python
class Maszyna(Protocol):
    async def wywolaj(self, makro: str) -> None:
        """Czeka na koniec makra. Błąd makra to `BladMakra` z treścią z Klippera."""

MAKRA_DOZWOLONE = re.compile(r"^(KALIBRUJ|POMIAR|STAN_SYSTEMU|ODBLOKUJ|PRZYGOTUJ( SZCZELINA=\d+(\.\d+)?)?"
                             r"|(GORA|DOL)_(5|1)MM)$")
```

## Testing Strategy

- **pytest:** logika cyklu na symulatorze, trwałość, kolejka, API serwisu, klient Moonrakera na
  atrapie serwera WebSocket.
- **Playwright:** każde zadanie ma scenariusz widoczny dla robotnika, na realnym backendzie z atrapami,
  z przyspieszonym czasem. Symulator steruje się przez `/api/dev/*`, dostępne wyłącznie z symulatorem.
- Zakres testów według Projektu §9. Bez progu procentowego pokrycia.

## Boundaries

- **Always:** do maszyny tylko makra z listy, sprawdzane przed wysłaniem; zdjęcie na dysku przed
  wysyłką; napis TEST na podstawie `zrodlo_wyniku` z serwera; testy i Playwright przed commitem.
- **Ask first:** zmiany w `docs/printer.cfg`, push na GitHuba, dodanie danych do repo, nowe ciężkie
  zależności, istotne odstępstwa od Projektu.
- **Never:** `MANUAL_STEPPER` i makra `_*` z aplikacji; automatyczny ruch po STOP; kalibracja bez
  naciśnięcia przycisku; prezentowanie atrapy jako wyniku; commit sekretów lub danych z `sesja_*`;
  `/api/dev/*` przy prawdziwej maszynie.

## Success Criteria

1. Świeży start lub restart maszyny zawsze zaczyna się od kalibracji; nie ma ścieżki omijającej.
2. Pełny cykl z ekranami 2–12 przechodzi bez znajomości nazw makr.
3. STOP działa na każdym ekranie. Po nim ruch następuje dopiero po przytrzymaniu „Wznów” przez 3 s
   i naciśnięciu kalibracji, a potem wymuszone jest czyszczenie.
4. Przerwanie cyklu na dowolnym kroku, także restartem backendu, wymusza czyszczenie przed następną próbką.
5. Co N czyszczeń (domyślnie 1) praca jest zablokowana do potwierdzenia opróżnienia pudełka.
6. Niedostępny serwer nie gubi zdjęcia; po powrocie wysyłka bez duplikatu, wynik widoczny na ekranie.
7. Wynik atrapy zawsze pokazuje „TEST – wynik niemiarodajny”.
8. Numery próbek rosną o 1 i nie powtarzają się po restarcie ani anulowaniu; skanowanie domyślnie wyłączone.
9. Aplikacja odrzuca każde makro spoza listy, zanim trafi do Moonrakera.
10. Kontener `mock` działa i przyjmuje zdjęcie; wariant `gpu` buduje się i raportuje GPU, jeśli środowisko je udostępnia.
11. Wszystkie testy przechodzą, a ekrany mieszczą się w 1280 × 800 bez przewijania.

## Open Questions

Nie blokują budowy, zostają do sprawdzenia na sprzęcie (Projekt §10): szczelina pomiarowa, czas spływu,
czasy makr, profil kamery dla nowej odległości, czas prawdziwej analizy.

**Poza testami na atrapach:** Moonraker jest przetestowany tylko na atrapie serwera, a `printer.cfg` nie był uruchamiany.
