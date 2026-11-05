# station — aplikacja stacji pomiarowej

Ekran dotykowy 1280 × 800 przy maszynie „Kostka mati”. Prowadzi robotnika krok po kroku: kalibracja,
wsypanie próbki, rozgarnianie, zdjęcie, wynik z serwera, czyszczenie stołu.

Działa na Raspberry Pi bez Dockera: backend FastAPI, UI React, zdjęcia silnikiem z
[../acquisition/](../acquisition/). Ocenę wykonuje [../service/](../service/).

Projekt: [../docs/superpowers/specs/2026-11-05-ui-stanowiska-design.md](../docs/superpowers/specs/2026-11-05-ui-stanowiska-design.md).

## Uruchomienie na zwykłym komputerze (atrapy)

```bash
python3 -m venv .venv && .venv/bin/pip install -r station/requirements-dev.txt -r service/requirements.txt
station/run-dev.sh      # UI: http://127.0.0.1:8100
```

Atrapy maszyny, kamery i analizy działają bez sprzętu i bez GPU.

## Uruchomienie przy maszynie

**Nie było jeszcze sprawdzane na sprzęcie.** `docs/printer.cfg` nie był uruchamiany, a klient
Moonrakera przeszedł testy tylko na atrapie serwera. Przed pierwszym użyciem przejdź listę z projektu
(§10), zwłaszcza szczelinę pomiarową i nowy profil kamery.

```bash
export STACJA_MASZYNA=moonraker
export STACJA_MOONRAKER=ws://127.0.0.1:7125/websocket
export STACJA_SERWIS=http://<serwer-gpu>:8000
export STACJA_DANE=~/stacja-dane
export GRAINCONTROL_PROFILE=~/graincontrol/profiles/acquisition/<profil>.json
PYTHONPATH=station .venv/bin/python -m uvicorn stacja.main:app --host 127.0.0.1 --port 8100
```

Instalacja trybu kiosk nie jest częścią tego etapu.

## Tryb serwisowy

Przytrzymaj napis „GrainControl” przez 5 s. Są tam ruchy stołu, podgląd kamery, ustawienia (czas spływu,
szczelina, opróżnianie co N, limit kolejki), przełącznik skanowania i reset numeracji.

## Testy

```bash
.venv/bin/python -m pytest station/tests service/tests -q
npm --prefix station/web ci && npm --prefix station/web run test:e2e
```

Po zmianach w `web/src` przebuduj UI (`npm --prefix station/web run build`) i dołącz `stacja/static`
do commita, bo Pi nie ma Node.
