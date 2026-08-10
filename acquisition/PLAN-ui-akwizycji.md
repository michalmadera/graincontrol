# Plan: UI akwizycji (warstwa 1) — kiosk Chromium + FastAPI + React

Realizacja `docs/spec-akwizycji.md §12`. Cel: aplikacja stanowiska badawczego do
zbierania materiału wg protokołu (§8–9), z kontraktem sprawdzanym po każdym ujęciu.

## Decyzje architektoniczne

- **Stos:** FastAPI (`uvicorn --workers 1`) + React (Vite → bundle statyczny serwowany
  przez FastAPI). Na Pi **bez node ani kroku budowania** — bundle budowany na dev.
- **Powłoka UI:** **kiosk Chromium** wskazujący na `http://localhost:PORT` (nie Electron/
  Tauri). Kamera jest zasobem lokalnym na Pi, więc FastAPI i tak musi tam chodzić; Chromium
  daje uczucie „apki" bez dodatkowego stacku. Ekran dotykowy **1024×600** (`notes.md`).
- **Kamera = zasób wyłączny:** jeden komponent szeregujący. Podgląd MJPEG (na parametrach
  profilu) i ujęcie nie działają jednocześnie — *zatrzymaj podgląd → ujęcie → QC → wznów*.
- **Backend reużywa istniejący kod, nie przepisuje go:**
  - `capture/captureSample.py` — silnik kontraktu (sesja, próbka, layout/frame, ujęcie,
    weryfikacja §5, archiwum atomowe §10/§11, manifest, journal). **DO USTALENIA z Michałem:**
    lekki refactor rozdzielający *silnik* (funkcje zwracające dane) od *CLI* (argparse+print),
    żeby FastAPI mógł go zaimportować. Fallback bez zmian w jego kodzie: wołanie jako subprocess
    + odczyt zapisanych `acquisition.json`/`manifest.csv`.
  - `qc/imageStats.py` — QC §6 (`max_dn`, `clip_frac`, `patch_present`, `patch_L_white`,
    `focus_metric`, `foreground_frac`…). **Wpięcie w przebieg ujęcia** — dziś `captureSample`
    zapisuje `qc: not_run`; UI orkiestruje kontrakt → QC → werdykt i zapis `qc.json`.
  - `calibration/{exposureAssistant,flatfieldCapture,scaleMeasure}.py` — kreatory (Faza 3).
  - `station.json` + `profiles/acquisition/P1-scientific-20260810.json` — konfiguracja gotowa.

## Layout (propozycja)

```
acquisition/
  server/            # FastAPI: API §12.11, menedżer kamery, pliki pochodne §12.10
    main.py  camera.py  derived.py  events.py  static/   (zbudowany bundle)
  web/               # źródła React (Vite) — budowane na dev, nie na Pi
  capture/  qc/  calibration/   (istniejące silniki, importowane przez server)
  deploy/            # systemd: graincontrol-acq.service + chromium-kiosk.service
```

## Fazy

### Faza 0 — Fundament i integracja
- [ ] Ustalić z Michałem: refactor `captureSample` na importowalny silnik vs subprocess; layout.
- [ ] Szkielet FastAPI (`--workers 1`), serwowanie bundla React ze `static/`.
- [ ] **Menedżer kamery**: jeden zamek; podgląd MJPEG (rpicam-vid/picamera2 na parametrach
      profilu — NIE automatyka) ↔ ujęcie; przejście zakomunikowane, żądanie w trakcie odrzucane.
- [ ] **Wpiąć QC (`imageStats` §6)** w przebieg: kontrakt (silnik) → QC → werdykt; zapis `qc.json`,
      `qc_status` do manifestu; `patch_present`/`focus_metric` = odrzucenie (§6).
- [ ] Testy bez kamery: atrapa `rpicam_still` w `station.json` (silnik już to wspiera).

### Faza 1 — Rdzeń sesji (MVP) = ekran `/session` end-to-end
- [ ] API: `POST/DELETE /api/session`, `PUT /api/session/sample`, `POST /api/session/layout`,
      `POST /api/capture` (kontrakt+QC+archiwum+werdykt), `GET /api/events` (SSE postęp),
      `GET /api/preview.mjpg`.
- [ ] Ekran `/session`: podgląd na żywo, panel próbki (dostawa/próbka/werdykt/etap/ułożenie/ujęcie),
      **dwa wielkie przyciski „ZRÓB ZDJĘCIE" / „PRZESYPAŁEM MATERIAŁ"** (frame_seq vs layout_seq),
      werdykt inline (zielony/czerwony+przyczyna), pasek historii ostatnich ujęć ze statusem QC.
- [ ] Sterowanie etapem protokołu: A blokuje „przesypałem", B monituje po ujęciu, E wymaga przyczyn.
- [ ] Blokada przycisku od wciśnięcia do werdyktu (brak podwójnego wyzwolenia).
- **Rezultat:** operator zbiera dane wg protokołu; to jest minimalny użyteczny produkt.

### Faza 2 — Weryfikacja ujęcia `/capture/<id>`
- [ ] Pliki pochodne §12.10 po ujęciu: `derived/{preview_1600.jpg, thumb_320.jpg, tiles/,
      qc_overlay.png, histogram.json}` (kasowalne, poza sumami kontrolnymi).
- [ ] Ekran: obraz z nakładkami (ROI wzorców/ostrości, mapa ≥245 DN), **zoom 1:1**, histogram
      (cel 220–230), tabela QC (wartość/próg/status), L\*a\*b\* wzorców, trendy dryfu sesji,
      porównanie z poprzednim i `reference_sample`, pełne metadane + linia polecenia.

### Faza 3 — Pozostałe ekrany
- [ ] `/archive` — filtrowanie (dostawa/próbka/sesja/etap/werdykt/QC/daty), eksport listy ścieżek
      do `measure.py`, „przebuduj indeks" z manifestu.
- [ ] `/profile` — wgląd; zmiana = kopia robocza → różnica → uzasadnienie → **nowy profile_id**
      (nadpisanie niemożliwe). `/profile/exposure` — asystent (wrapper `exposureAssistant.py`).
- [ ] `/calibration` — kreatory flat-field / skala / colorchart / dark / reference_sample
      (wrappery `flatfieldCapture.py`, `scaleMeasure.py`); stan kalibracji profilu.
- [ ] `/report` — postęp etapów A–F, dryf, odrzucenia zagregowane; `/diagnostics` — wersje,
      dysk, log, kopia zapasowa.

### Faza 4 — Kiosk i odporność
- [ ] `deploy/`: systemd dla FastAPI + `chromium --kiosk`; autostart, ukrycie kursora.
- [ ] Wznowienie przerwanej sesji (stan w pliku — silnik już to ma), kontrola dysku, przenoszenie
      `.tmp/` po zaniku zasilania (silnik ma `recover_interrupted`).
- [ ] Konflikt o kamerę (§12.9): żądanie w trakcie przełączania odrzucane, nie kolejkowane.
- [ ] Druga karta = tryb tylko do odczytu (stan sesji w `session.json`, nie w przeglądarce).

## Kryteria odbioru (z §14 spec-akwizycji)
Wymuszanie parametrów (10 ujęć identyczne), wykrywanie naruszenia/braku wzorca/rozjechanej
ostrości, poprawność liczników (3×3), integralność przy zaniku zasilania, wznowienie, odporność
UI na odświeżenie, konflikt o kamerę, odtwarzalność `derived/`, ochrona profilu, **zgodność z
warstwą 2** (`measure.py` bez `--allow-missing-metadata` → status kontraktu `ok`).

## Poza tym planem (na teraz)
Warstwa 2/3/4 (pomiar, kalibracja progów, system operacyjny) — osobne tory. Trening modelu
segmentacji (cellpose/grainnet) — osobny tor, nie miesza się z archiwum pomiarowym barwy.
