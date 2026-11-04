# Wymiana kamery → nowy profil (checklista)

Nowa kamera/optyka = **nowy profil**. Profil to plik JSON w `profiles/acquisition/`
składany **ręcznie**, ale nie wymyślasz liczb — skrypty kalibracji **mierzą i wypisują
gotowe linie** do wklejenia (`Do profilu — ... "pole": wartość`). Nie nadpisuj aktywnego
profilu, twórz **nowy `profile_id`**.

Wszystko robisz przy stanowisku, z nową kamerą i **kartą wzorcową (biel+szarość) w kadrze**.

## 0. Start
```bash
cd ~/graincontrol
cp profiles/acquisition/P2-scientific-20260813.json \
   profiles/acquisition/P3-scientific-$(date +%Y%m%d).json   # nowy profil = kopia szablonu
```
Otwórz nowy plik do edycji — będziesz wklejał do niego wartości z kolejnych kroków.
Zmień `profile_id` na `P3-scientific-<data>`. Sprawdź `camera`/`resolution`/`tuning_file`
(patrz sekcja „Inny sensor").

## 1. Ostrość — ustaw i zablokuj
```bash
python3 podglad_ostrosci.py     # (z repo kamyki) kręć aż max ostrości, zablokuj obiektyw
```
Ostrość ma być **równa po całym kadrze** (nie tylko w centrum) — patrz heatmapy ostrości.
W profilu: `optics.focus = "zablokowana"`.

## 2. Ekspozycja → `shutter_us`
```bash
python3 acquisition/calibration/exposureAssistant.py \
  -c acquisition/capture/station.json --from 40000 --to 110000 --steps 8
```
Dobierasz czas tak, żeby **biel karty ~220–230 DN** (nowa kamera ma inną czułość).
Skrypt wypisze `"shutter_us": <wartość>` → **wklej do profilu**. Odczytaj też `awb_gains`
(balans bieli) z klatki karty i wpisz w `awb_gains`.

## 3. Skala mm/px → `scale_id`
```bash
python3 acquisition/calibration/scaleMeasure.py -c acquisition/capture/station.json --shoot
# odczytaj współrzędne z preview_grid.png, potem:
python3 acquisition/calibration/scaleMeasure.py -c acquisition/capture/station.json \
  --calib scale_<id> --pair x1,y1,x2,y2,mm --pair x1,y1,x2,y2,mm
```
Podaj **kilka par** na różnych wysokościach kadru (rozrzut = miara skosu). Skrypt wypisze
`"scale_id": <id>` → wklej w `calibration.scale_id`. Zaktualizuj też `optics.distance_mm`
i `focal_length` jeśli się zmieniły.

## 4. Flat-field (winietowanie) → `flatfield_id`  **[obowiązkowe]**
```bash
python3 acquisition/calibration/flatfieldCapture.py -c acquisition/capture/station.json --frames 10
```
Strojenie scientific nie ma ALSC → bez tego winietowania nie ma w torze. Skrypt wypisze
`"flatfield_id": <id>` → wklej w `calibration.flatfield_id`.

## 5. ROI karty + wartości oczekiwane (ręcznie z klatki karty)
Nowe kadrowanie = **karta w innym miejscu** → stare ROI są nieważne.
- z klatki karty odczytaj prostokąty `white` i `grey` → wpisz w `reference_patches[].roi`
  (wciej ~6 px od krawędzi pola, bo karta bywa obrócona 0,5–1,3°),
- zmierz `white_patch_L` (L\* bieli po zakotwiczeniu) i `max_dn` → wpisz w `expected`.

## 6. Wskaż nowy profil serwerowi
Domyślny profil to `P2-...` (`server/config.py`). Nie ruszaj kodu — użyj zmiennej:
```bash
GRAINCONTROL_PROFILE=~/graincontrol/profiles/acquisition/P3-scientific-<data>.json \
PYTHONPATH=acquisition ~/gc-venv/bin/python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
```
Serwer wczyta profil i **sprawdzi kontrakt po każdym ujęciu** — jak coś się nie zgadza,
UI pokaże przyczynę (nie ubija się).

## Inny sensor (nie imx477)
Jeśli nowa kamera ma **inny sensor**, oprócz powyższego zmień w profilu:
- `camera`, `resolution`,
- `tuning_file` (ścieżka do właściwego pliku strojenia libcamera) **oraz** `tuning_file_sha256`
  (policz: `sha256sum <tuning_file>`),
- zweryfikuj, że plik strojenia jest „scientific"/liniowy (bez podbicia kontrastu/ostrości).

## Kolejność w skrócie
ostrość → ekspozycja(`shutter_us`,`awb_gains`) → skala(`scale_id`) → flat-field(`flatfield_id`)
→ ROI karty + `expected` → wskaż profil serwerowi. Skrypty mierzą i wypisują; Ty wklejasz do
nowego JSON-a.
