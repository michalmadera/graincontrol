# Narzędzie akwizycji — serwer

Proste narzędzie do zbierania zdjęć do zbioru danych. Apka webowa (FastAPI + React),
na cały ekran. **Nie** jest to system produkcyjny ani tor badawczy z kontraktem/QC —
to lekki zbieracz zdjęć.

## Workflow

```
START SESJI            → folder  dane/sesja_YYYYMMDD_HHMM/
wpisz nazwę: BAD       → podfolder BAD/
ZDJĘCIE ×N (przesypuj) → BAD/BAD_1.png + BAD_1.dng, BAD_2…, BAD_3…
zmień nazwę: NICE      → NICE/NICE_1.png + NICE_1.dng …
```

Parametry kamery są **zamrożone z profilu** (czas, wzmocnienia, AWB, plik strojenia,
ISP bez wyostrzania/denoise) — powtarzalna akwizycja. `--raw` zapisuje DNG obok PNG.

## Uruchomienie

### Dev (bez Pi, atrapa kamery)
```bash
pip install -r acquisition/server/requirements.txt
acquisition/server/run-dev.sh          # http://127.0.0.1:8000
```
Bez `rpicam-still` w systemie zdjęcia są syntetyczne (atrapa) — cały przepływ da się
przeklikać. Zdjęcia lądują w `dane/` (poza repo, w `.gitignore`).

### Pi (prawdziwa kamera)
```bash
pip install -r acquisition/server/requirements.txt
export PYTHONPATH=acquisition
uvicorn server.main:app --host 0.0.0.0 --port 8000
```
Wymaga `rpicam-apps` i pliku strojenia z profilu. Konfiguracja przez zmienne:
`GRAINCONTROL_PROFILE` (domyślnie P1-scientific), `GRAINCONTROL_DANE` (domyślnie `dane/`),
`GRAINCONTROL_DUMMY=1` (wymuś atrapę).

## Moduły
| plik | rola |
|---|---|
| `config.py` | profil (parametry kamery) + katalog danych |
| `capture.py` | sesja → etykieta (podfolder) → zdjęcie PNG+DNG, miniatury |
| `camera.py` | podgląd MJPEG ⇄ zdjęcie pod jednym zamkiem (kamera = zasób wyłączny) |
| `main.py` | API: `/api/state`, `/api/session`, `/api/label`, `/api/shoot`, `/api/thumb`, `/api/preview.mjpg` |

## Test
```bash
python3 acquisition/server/tests/test_capture.py   # przepływ na atrapie
```
