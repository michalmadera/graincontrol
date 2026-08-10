# Serwer UI akwizycji

Backend UI stanowiska akwizycji (`docs/spec-akwizycji.md §12`). FastAPI
(`uvicorn --workers 1`) + bundle React serwowany statycznie. Offline, kiosk.

## Stan: Faza 0 (fundament)

Zbudowane i przetestowane bez kamery:

| moduł | rola | §spec |
|---|---|---|
| `config.py` | wczytanie `station.json` + profilu | §3 |
| `qc.py` | orkiestrator QC: miary `imageStats` + progi → werdykt, `qc.json` | §6 |
| `camera.py` | menedżer kamery: podgląd MJPEG ⇄ ujęcie pod jednym zamkiem | §12.9 |
| `events.py` | szyna SSE (postęp ujęcia, stan kamery) | §12.11 |
| `capture_engine.py` | owijka subprocess na `captureSample.py` (kontrakt §5, archiwum) | §5,§10 |
| `main.py` | app, `/api/health`, `/api/status`, `/api/profile`, `/api/preview.mjpg`, `/api/events` | §12.11,§12.12 |

**Integracja z silnikiem:** subprocess-first — serwer woła `captureSample.py` i czyta
`manifest.csv`/`capture.png`, **bez zmian w kodzie Michała**. Kontrakt (§5) liczy silnik;
QC (§6) to osobna bramka po zapisie. Docelowy refactor silnika na część importowalną —
do uzgodnienia (patrz `../PLAN-ui-akwizycji.md`).

## Uruchomienie (dev, bez Pi)

```bash
pip install -r acquisition/server/requirements.txt
export GRAINCONTROL_STATION=acquisition/capture/station.json
export PYTHONPATH=acquisition
uvicorn server.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Bez `rpicam-vid` w systemie podgląd używa `DummyBackend` (syntetyczne klatki),
więc UI da się rozwijać na maszynie deweloperskiej. Wymuszenie atrapy:
`"camera_backend": "dummy"` w `station.json`.

## Testy

```bash
python3 acquisition/server/tests/test_qc.py     # QC §6 na syntetycznych kadrach
```

## Dalej

- **Faza 1 (MVP):** API sesji (`POST/DELETE /api/session`, `PUT /api/session/sample`,
  `POST /api/session/layout`, `POST /api/capture`) + ekran `/session` (podgląd, dwa
  wielkie przyciski, werdykt inline). Bundle React ląduje w `static/`.
- Fazy 2–4: patrz `../PLAN-ui-akwizycji.md`.
