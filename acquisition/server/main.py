"""Serwer UI akwizycji — FastAPI (`uvicorn --workers 1`).

Faza 0: szkielet, konfiguracja, stan stanowiska (§12.12 pasek stanu), podgląd
MJPEG i szyna zdarzeń, serwowanie bundla React ze `static/`. API sesji/ujęcia
(§12.11) i ekrany wchodzą w Fazie 1 — tu są tylko fundamenty, na których staną.

Uruchomienie:
    GRAINCONTROL_STATION=acquisition/capture/station.json \\
    uvicorn acquisition.server.main:app --host 0.0.0.0 --port 8000 --workers 1
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .camera import CameraManager, make_backend
from .capture_engine import CaptureEngine
from .config import load_config
from .events import EventBus
from .session import build_router

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _station_path() -> str:
    env = os.environ.get("GRAINCONTROL_STATION")
    if env:
        return env
    return str(Path(__file__).resolve().parent.parent / "capture" / "station.json")


def create_app() -> FastAPI:
    config = load_config(_station_path())
    events = EventBus()
    camera = CameraManager(make_backend(config.profile, config.station))
    engine = CaptureEngine(config)

    app = FastAPI(title="GrainControl — akwizycja", version="0.0-faza0")
    app.state.config = config
    app.state.events = events
    app.state.camera = camera
    app.state.engine = engine

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "phase": "faza0"}

    @app.get("/api/status")
    def status() -> dict:
        """Pasek stanu (§12.12): kamera, dysk, plik strojenia, profil."""
        archive = config.archive_root
        # dysk z najbliższego istniejącego rodzica — archiwum może jeszcze nie istnieć
        probe = archive
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        disk = shutil.disk_usage(probe) if probe.exists() else None
        tuning = Path(config.profile["tuning_file"])
        return {
            "profile_id": config.profile_id,
            "study_id": config.study_id,
            "operator": config.station.get("operator"),
            "camera": camera.snapshot(),
            "archive_root": str(archive),
            "archive_exists": archive.exists(),
            "disk_free_gb": round(disk.free / 2**30, 2) if disk else None,
            "tuning_file": str(tuning),
            "tuning_present": tuning.exists(),
            "study": config.station.get("study"),
            "calibration_missing": [k for k in ("flatfield_id", "scale_id")
                                    if not config.profile.get("calibration", {}).get(k)],
        }

    @app.get("/api/profile")
    def profile() -> dict:
        return config.profile

    @app.get("/api/preview.mjpg")
    async def preview() -> StreamingResponse:
        return StreamingResponse(
            camera.preview_stream(),
            media_type="multipart/x-mixed-replace; boundary=frame")

    @app.get("/api/events")
    async def event_stream() -> StreamingResponse:
        return StreamingResponse(events.subscribe(), media_type="text/event-stream")

    # API sesji/próbki/ujęcia (§12.11) — przed montowaniem statyki na "/".
    app.include_router(build_router(app.state))

    # Bundle React serwowany statycznie ze `static/`.
    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="ui")

    return app


app = create_app()
