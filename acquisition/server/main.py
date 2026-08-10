"""Serwer prostego narzędzia akwizycji — FastAPI + React (apka webowa na cały ekran).

Przepływ: START SESJI → wpisz nazwę (BAD/NICE…) → ZDJĘCIE ×N → zmień nazwę → …
Zapis PNG+DNG na zamrożonych parametrach do `dane/sesja_.../NAZWA/`.

Uruchomienie:
    uvicorn acquisition.server.main:app --host 0.0.0.0 --port 8000
    # bez kamery (dev):  GRAINCONTROL_DUMMY=1 uvicorn ...
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .camera import CameraBusy, CameraManager, make_backend
from .capture import CaptureController
from .config import load_config

STATIC_DIR = Path(__file__).resolve().parent / "static"


class LabelBody(BaseModel):
    name: str


def create_app() -> FastAPI:
    config = load_config()
    camera = CameraManager(make_backend(config))
    controller = CaptureController(config)

    app = FastAPI(title="GrainControl — akwizycja", version="1.0-prosta")

    @app.get("/api/state")
    def state() -> dict:
        return {**controller.state(), "camera": camera.snapshot(),
                "data_root": str(config.data_root),
                "profile_id": config.profile.get("profile_id"),
                "dummy": controller._use_dummy()}

    @app.post("/api/session")
    def start_session() -> dict:
        return {**controller.start_session(), "camera": camera.snapshot()}

    @app.post("/api/label")
    def set_label(body: LabelBody) -> dict:
        try:
            return controller.set_label(body.name)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/shoot")
    async def shoot() -> dict:
        if controller.session_dir is None or controller.label is None:
            raise HTTPException(409, "Ustaw sesję i nazwę przed zdjęciem.")
        try:
            return await camera.run_exclusive(controller.shoot)
        except CameraBusy as exc:
            raise HTTPException(409, str(exc))
        except RuntimeError as exc:
            raise HTTPException(500, str(exc))

    @app.get("/api/thumb/{label}/{index}")
    def thumb(label: str, index: int) -> FileResponse:
        path = controller.thumb_path(label, index)
        if path is None:
            raise HTTPException(404, "Brak miniatury.")
        return FileResponse(path)

    @app.get("/api/preview.mjpg")
    async def preview() -> StreamingResponse:
        return StreamingResponse(
            camera.preview_stream(),
            media_type="multipart/x-mixed-replace; boundary=frame")

    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="ui")

    return app


app = create_app()
