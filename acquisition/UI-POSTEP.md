# Narzędzie akwizycji — jak uruchomić

Stan na 2026-08-10. **Proste narzędzie do zbierania zdjęć** (nie tor badawczy z
kontraktem/QC, nie system produkcyjny). Apka webowa na cały ekran: FastAPI + React.

## Co robi

```
START SESJI            → folder  dane/sesja_YYYYMMDD_HHMM/
wpisz nazwę: BAD       → podfolder BAD/
ZDJĘCIE ×N (przesypuj) → BAD/BAD_1.png + BAD_1.dng, BAD_2…, BAD_3…
zmień nazwę: NICE      → NICE/NICE_1.png + NICE_1.dng …
```

Zdjęcia na **zamrożonych parametrach profilu** (powtarzalne). Każde ujęcie = PNG + DNG.

## Jak uruchomić — DEV (ten komputer, bez Pi)

```bash
pip install -r acquisition/server/requirements.txt   # raz
acquisition/server/run-dev.sh
```

Otwórz **http://127.0.0.1:8000**. Bez kamery podgląd i zdjęcia są syntetyczne (atrapa),
ale cały przepływ działa i pliki realnie lądują w `dane/sesja_.../NAZWA/`.

Klikasz: **START SESJI** → wpisujesz **BAD** → **USTAW NAZWĘ** → **ZRÓB ZDJĘCIE** kilka
razy → **zmień nazwę** → **NICE** → itd. Po prawej licznik zapisanych i miniatura ostatniego.

## Jak uruchomić — Pi (prawdziwa kamera)

```bash
export PYTHONPATH=acquisition
uvicorn server.main:app --host 0.0.0.0 --port 8000
```
Wymaga `rpicam-apps` + pliku strojenia z profilu. Zmienne: `GRAINCONTROL_PROFILE`,
`GRAINCONTROL_DANE`, `GRAINCONTROL_DUMMY=1`.

## Test
```bash
python3 acquisition/server/tests/test_capture.py
```

## Uwaga o zakresie
To narzędzie celowo pomija maszynerię z `spec-akwizycji.md §12` (kontrakt metadanych §5,
QC §6, protokół A–F, słowniki werdyktów, manifest, kiosk). Tamto to **tor badawczy** i
**system produkcyjny** — osobne, cięższe rzeczy. Tu chodzi o szybkie zebranie zdjęć z
etykietą klasy (BAD/NICE/…). Pełna wizja §12 opisana w `PLAN-ui-akwizycji.md` (odłożona).
