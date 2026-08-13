# Narzędzie akwizycji — serwer

Apka webowa (FastAPI + React) na cały ekran, do zbierania materiału przy stanowisku.
Zdjęcia robi **tym samym silnikiem co CLI** (`../capture/captureSample.py`): ta sama
linia polecenia, ten sam kontrakt akwizycji sprawdzany po każdym ujęciu, te same
metadane i sumy kontrolne. Ergonomia jest własna — sesja → nazwa → seria — bo przy
stanowisku liczy się liczba dotknięć ekranu, a nie kompletność modelu danych.

## Workflow

```
START SESJI            → folder  dane/sesja_YYYYMMDD_HHMM/
wpisz nazwę: BAD       → podfolder BAD/
ZDJĘCIE ×N (przesypuj) → BAD/BAD_1.png + .dng + _meta.json + _acquisition.json + .sha256
zmień nazwę: NICE      → NICE/NICE_1.png …
```

Ujęcie niezgodne z profilem trafia do `odrzucone/<NAZWA>/` razem z przyczyną i **nie
zwiększa numeru** — operator powtarza je, a numeracja zostaje ciągła. Sesja ma
`manifest.csv` (wiersz na ujęcie) i `journal.jsonl` (dziennik dopisywany).

## Co jest sprawdzane po każdym ujęciu

Kontrakt akwizycji z `docs/spec-akwizycji.md` §5, liczony z metadanych `rpicam-still`:

| pole | reguła |
|---|---|
| `ExposureTime`, `AnalogueGain`, `ColourGains` | = profil, ±1% |
| `DigitalGain` | 1,000 ±0,01 — inaczej ISP kompensował ekspozycję cyfrowo |
| `ColourCorrectionMatrix` | identyczna jak w pierwszym ujęciu sesji |
| `Lux` | ostrzeżenie przy zmianie > 5% w sesji |

Parametry ISP (`--sharpness`, `--denoise`, `--saturation`, `--contrast`,
`--brightness`) nie wracają w metadanych, więc jedynym dowodem ich ustawienia jest
zapisana linia polecenia — trafia do `_command_line` w `*_meta.json`.

**Blokady.** Brak pliku strojenia z profilu, niezgodna jego suma kontrolna albo
niekompletny profil blokują zdjęcia i są widoczne stałym czerwonym paskiem w UI.
Serwer wstaje mimo błędu, żeby móc pokazać przyczynę.

**Czego nie ma:** QC §6 (obecność wzorców, ostrość, przesterowanie) — obraz nie jest
otwierany. Nie ma też identyfikatorów z §2 (`batch_id`, `sample_id`, werdykt eksperta,
`layout_seq`/`frame_seq`); nazwa etykiety zastępuje je jednym polem.

## Uruchomienie

### Dev (bez Pi, atrapa kamery)
```bash
pip install -r acquisition/server/requirements.txt
acquisition/server/run-dev.sh          # http://127.0.0.1:8000
```
Bez `rpicam-still` w systemie zdjęcia są syntetyczne, a metadane budowane z profilu, więc
cały przepływ — łącznie z kontraktem — da się przeklikać. Takie ujęcia mają `_dummy: true`
w metadanych i w rekordzie, żeby nigdy nie zostały wzięte za materiał pomiarowy.

### Pi (prawdziwa kamera)
```bash
pip install -r acquisition/server/requirements.txt
export PYTHONPATH=acquisition
uvicorn server.main:app --host 0.0.0.0 --port 8000
```
Wymaga `rpicam-apps` i pliku strojenia **wskazanego w profilu** — nie jest już
podmieniany autowykrywaniem, bo domyślny `imx477.json` to inna krzywa tonalna i inne
macierze CCM. Konfiguracja przez zmienne: `GRAINCONTROL_PROFILE` (domyślnie
P2-scientific-20260813), `GRAINCONTROL_DANE` (domyślnie `dane/`), `GRAINCONTROL_DUMMY=1`.

## Moduły
| plik | rola |
|---|---|
| `engine.py` | most do `captureSample.py` — jedno źródło linii polecenia i kontraktu |
| `config.py` | profil ze sprawdzeniem kompletności i sumy strojenia, katalog danych |
| `capture.py` | sesja → etykieta → ujęcie, kontrakt, sumy, manifest, dziennik |
| `camera.py` | podgląd MJPEG ⇄ zdjęcie pod jednym zamkiem (kamera = zasób wyłączny) |
| `main.py` | API: `/api/state`, `/api/session`, `/api/label`, `/api/shoot`, `/api/thumb`, `/api/preview.mjpg` |

## Test
```bash
python3 acquisition/server/tests/test_capture.py
```
Sprawdza linię polecenia, wzbogacenie metadanych, kontrakt, sumy kontrolne, ścieżkę
odrzucenia bez zwiększenia numeru i odzyskiwanie przerwanego zapisu.
