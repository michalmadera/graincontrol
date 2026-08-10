# UI akwizycji — postęp i jak uruchomić

Stan na 2026-08-10. Plan całości: [`PLAN-ui-akwizycji.md`](PLAN-ui-akwizycji.md).
Stos: FastAPI (`uvicorn --workers 1`) + React (Vite → bundle w `server/static/`),
kiosk Chromium. Zgodnie z `docs/spec-akwizycji.md §12`.

## Jak uruchomić — DEV (ten komputer, bez Pi)

Na maszynie bez kamery używamy **atrapy** `rpicam-still` (emituje syntetyczny kadr
z wzorcami i metadanymi kontraktu), więc cały przepływ da się przeklikać.

```bash
# 1. zależności Pythona (raz)
pip install -r acquisition/server/requirements.txt

# 2. (opcjonalnie) przebuduj frontend — bundle i tak jest w repo
cd acquisition/web && npm install && npm run build && cd ../..

# 3. start serwera dev z atrapą kamery
acquisition/server/run-dev.sh
```

Potem otwórz **http://127.0.0.1:8000** w przeglądarce. Zobaczysz ekran sesji:

1. **START SESJI** → w oknie zaznacz „startuję bez kalibracji" (profil dev nie ma
   flat-fielda) → ROZPOCZNIJ.
2. **DEKLARUJ PRÓBKĘ** → wypełnij pola (dostawa, próbka, dostawca, materiał,
   oceniający), wybierz werdykt i etap → ZAPISZ PRÓBKĘ.
3. **ZRÓB ZDJĘCIE** → przycisk pokazuje etapy (zatrzymanie podglądu → ekspozycja →
   zapis), po chwili pojawia się **werdykt** (zielony = zapisane; żółty = QC odrzuca;
   czerwony = kontrakt/błąd) i ujęcie ląduje na pasku historii.
4. **PRZESYPAŁEM MATERIAŁ** → zwiększa ułożenie (nowy `layout_seq`).

> Podgląd na dev to szara syntetyczna klatka (atrapa). Na Pi to strumień MJPEG z
> kamery na parametrach profilu.

Inny port: `PORT=8100 acquisition/server/run-dev.sh`.

## Jak uruchomić — Pi (docelowo)

```bash
export GRAINCONTROL_STATION=acquisition/capture/station.json
export PYTHONPATH=acquisition
uvicorn server.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Wymaga `rpicam-apps` i pliku strojenia z profilu (sha256 sprawdzany). Autostart
kiosku (systemd + `chromium --kiosk`) dopiero w Fazie 4.

## Postęp faz

| faza | zakres | stan | commit |
|---|---|---|---|
| — | Plan UI | ✅ | `008e936` |
| 0 | Fundament: serwer, QC §6, menedżer kamery, SSE, owijka silnika | ✅ | `22feb3a` |
| 1 | **MVP:** API sesji + ekran `/session` (React) | ✅ | `653ecfa` |
| 2 | Weryfikacja ujęcia `/capture/<id>` (pliki pochodne, zoom, histogram, tabela QC) | ⏳ w toku | — |
| 3 | Ekrany `/archive`, `/profile`, `/calibration`, `/report`, `/diagnostics` | ⬜ | — |
| 4 | Kiosk + odporność (systemd, wznowienie, druga karta read-only) | ⬜ | — |

### Co konkretnie działa (Faza 0–1)

- **API §12.11:** `POST/DELETE /api/session`, `PUT /api/session/sample`,
  `POST /api/session/layout`, `POST /api/capture`, `GET /api/captures`,
  `GET /api/status`, `GET /api/profile`, `GET /api/preview.mjpg`, `GET /api/events` (SSE).
- **Ekran sesji §12.3:** podgląd, panel próbki, dwa wielkie przyciski, werdykt inline,
  pasek historii, etapy A/B/E, modale start-sesji i deklaracji próbki (słowniki §8).
- **QC §6:** wszystkie miary z tabeli (max_dn, clip, wzorce, ostrość, foreground, dryf)
  → werdykt + `qc.json`. Kontrakt §5 liczy silnik `captureSample`, QC to osobna bramka.
- **Menedżer kamery §12.9:** podgląd ⇄ ujęcie pod jednym zamkiem; konflikt odrzucany.

## Testy (bez Pi)

```bash
python3 acquisition/server/tests/test_qc.py            # QC §6 na syntetycznych kadrach
python3 acquisition/server/tests/test_capture_flow.py  # pełny przepływ przez captureSample
```

## Do uzgodnienia z Michałem (dotyka jego kodu/architektury)

1. **Refactor silnika** `captureSample.py` na część importowalną + CLI. Dziś integracja
   jest subprocess-first (serwer woła CLI, czyta `manifest.csv`/`capture.png`) — działa,
   ale import byłby czystszy i szybszy.
2. **QC-reject a `frame_seq`/archiwum.** Silnik akceptuje po kontrakcie (§5) i od razu
   inkrementuje `frame_seq` oraz zapisuje do `captures/`. QC (§6) liczymy po zapisie jako
   osobną bramkę i dokładamy `qc.json`. Spec §12.3 chce, by odrzucenie **nie** zwiększało
   `frame_seq` — to wymaga QC wewnątrz silnika albo przejęcia całego zapisu przez UI.
3. **Start sesji** jest w silniku sprzężony z pierwszą operacją (nie ma czystego „tylko
   start"). Serwer obchodzi to, dokładając parametry sesji do pierwszej deklaracji próbki.
