"""API sesji, próbki, ujęcia (§12.11) — router FastAPI napędzający ekran /session.

Sprzężenie z silnikiem: `captureSample` tworzy `session.json` dopiero przy pierwszej
realnej operacji (deklaracja próbki / ujęcie), czytając wtedy parametry sesji z
argumentów. Dlatego `POST /api/session` **zapamiętuje** parametry sesji (operator,
warunki, zgoda na brak kalibracji §7), a serwer dokłada je do pierwszego wywołania
silnika. Źródłem prawdy o trwającej sesji jest `session.json` w archiwum (§12.12),
nie stan przeglądarki.

Werdykt ujęcia łączy dwie bramki: kontrakt metadanych (§5, liczy silnik) i QC (§6,
liczy `qc.py` po zapisie). Uzgodnienie polityki „QC-reject a `frame_seq`/archiwum"
z autorem silnika jest odnotowane w planie — tu QC zapisujemy jako `qc.json` obok
rekordu (poza sumami kontrolnymi) i zwracamy oba statusy uczciwie.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .camera import CameraBusy
from .qc import qc_from_png


class SessionStart(BaseModel):
    operator: str | None = None
    temperature: float | None = None
    illuminator_on_since: str | None = None
    session_notes: str | None = None
    no_calibration: bool = False


class SampleDeclare(BaseModel):
    batch: str
    sample: str
    supplier: str
    material: str
    verdict: str
    verdict_author: str
    stage: str
    reasons: str | None = None
    verdict_date: str | None = None
    notes: str | None = None


def _read_session_json(study_dir: Path) -> dict | None:
    path = study_dir / "session.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _manifest_rows(study_dir: Path) -> list[dict]:
    manifest = study_dir / "manifest.csv"
    if not manifest.exists():
        return []
    with manifest.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def build_router(state) -> APIRouter:
    """state: app.state z .config/.engine/.camera/.events; _pending trzymamy tu."""
    router = APIRouter(prefix="/api")
    config = state.config
    engine = state.engine
    camera = state.camera
    events = state.events
    state.pending_session = None  # parametry sesji do pierwszego wywołania silnika

    def session_view() -> dict:
        real = _read_session_json(config.study_dir)
        if real is not None:
            return {"status": "open", **real}
        if state.pending_session is not None:
            return {"status": "pending", **state.pending_session.model_dump()}
        return {"status": "none"}

    def _first_call_kwargs() -> dict:
        """Parametry sesji dokładane do pierwszej operacji, jeśli sesji jeszcze nie ma."""
        if _read_session_json(config.study_dir) is not None or state.pending_session is None:
            return {}
        p = state.pending_session
        kwargs = {"operator": p.operator, "temperature": p.temperature,
                  "illuminator_on_since": p.illuminator_on_since,
                  "session_notes": p.session_notes}
        if p.no_calibration:
            kwargs["no_calibration"] = True
        return {k: v for k, v in kwargs.items() if v not in (None, "")}

    # ------------------------------------------------------------------ sesja
    @router.get("/session")
    def get_session() -> dict:
        return session_view()

    @router.post("/session")
    def start_session(body: SessionStart) -> dict:
        if _read_session_json(config.study_dir) is not None:
            raise HTTPException(409, "Sesja już otwarta — zamknij ją przed startem nowej.")
        state.pending_session = body
        events.publish("session", status="pending")
        return session_view()

    @router.delete("/session")
    async def end_session() -> dict:
        real = _read_session_json(config.study_dir)
        if real is None:
            state.pending_session = None
            return {"status": "none"}
        result = await engine.end_session()
        if not result.ok:
            raise HTTPException(500, result.stderr.strip() or "Nie zamknięto sesji.")
        state.pending_session = None
        events.publish("session", status="closed")
        return {"status": "closed", "report": result.stdout.strip(),
                "counts": real.get("counts")}

    # ------------------------------------------------------------------ próbka
    @router.put("/session/sample")
    async def declare_sample(body: SampleDeclare) -> dict:
        if _read_session_json(config.study_dir) is None and state.pending_session is None:
            raise HTTPException(409, "Najpierw wystartuj sesję (POST /api/session).")
        result = await engine.declare_sample(**body.model_dump(), **_first_call_kwargs())
        if not result.ok:
            raise HTTPException(422, result.stderr.strip() or "Deklaracja odrzucona.")
        events.publish("sample", **session_view().get("sample", {}))
        return session_view()

    @router.post("/session/layout")
    async def advance_layout() -> dict:
        session = _read_session_json(config.study_dir)
        if session is None:
            raise HTTPException(409, "Brak otwartej sesji.")
        if session.get("sample") is None:
            raise HTTPException(409, "Brak zadeklarowanej próbki.")
        if session["sample"].get("protocol_stage") == "A":
            raise HTTPException(409, "Etap A — „przesypałem” zablokowane (§9).")
        result = await engine.advance_layout()
        if not result.ok:
            raise HTTPException(422, result.stderr.strip() or "Nie zmieniono ułożenia.")
        events.publish("layout", **session_view().get("sample", {}))
        return session_view()

    # ------------------------------------------------------------------ ujęcie
    @router.post("/capture")
    async def capture() -> dict:
        session = _read_session_json(config.study_dir)
        if session is None or session.get("sample") is None:
            raise HTTPException(409, "Brak otwartej sesji z zadeklarowaną próbką.")

        prev_mean = _previous_mean_dn(config.study_dir, session["session_id"])

        async def work() -> dict:
            events.publish("capture", stage="exposure")
            result = await engine.capture()
            events.publish("capture", stage="save")
            return _finalize_capture(result, prev_mean)

        try:
            events.publish("capture", stage="preview_stop")
            verdict = await camera.run_exclusive(
                work, on_state=lambda s: events.publish("camera", state=s))
        except CameraBusy as exc:
            raise HTTPException(409, str(exc))
        events.publish("capture", stage="verdict", **verdict)
        return verdict

    def _finalize_capture(result, prev_mean) -> dict:
        row = engine.last_manifest_row() or {}
        capture_id = row.get("capture_id")
        contract_status = row.get("contract_status")
        capture_dir = engine.capture_dir(capture_id) if capture_id else None

        qc = None
        if capture_dir is not None:
            image = capture_dir / f"capture.{config.profile.get('encoding', 'png')}"
            if image.exists():
                events_stage = qc_from_png(image, config.profile, prev_mean_dn=prev_mean)
                qc = events_stage
                try:
                    (capture_dir / "qc.json").write_text(
                        json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8")
                except OSError:
                    pass

        # Werdykt łączny: błąd silnika > odrzucenie kontraktu > odrzucenie QC > ok.
        if result.exit_code == 1:
            verdict = "error"
        elif result.rejected or contract_status not in (None, "ok"):
            verdict = "rejected"
        elif qc is not None and qc["status"] == "rejected":
            verdict = "qc_rejected"
        else:
            verdict = "ok"

        return {
            "capture_id": capture_id,
            "verdict": verdict,
            "contract_status": contract_status,
            "qc": qc,
            "accepted": verdict == "ok",
            "engine_stdout": result.stdout.strip(),
            "engine_stderr": result.stderr.strip() if not result.ok else "",
            "counts": (_read_session_json(config.study_dir) or {}).get("counts"),
        }

    # ------------------------------------------------------------- historia
    @router.get("/captures")
    def list_captures(session: str | None = None, limit: int = 20) -> dict:
        rows = _manifest_rows(config.study_dir)
        if session:
            rows = [r for r in rows if r.get("session_id") == session]
        return {"captures": rows[-limit:][::-1]}

    return router


def _previous_mean_dn(study_dir: Path, session_id: str) -> float | None:
    """mean_dn ostatniego zaakceptowanego ujęcia sesji — do miary dryfu QC (§6)."""
    rows = _manifest_rows(study_dir)
    for row in reversed(rows):
        if row.get("session_id") != session_id:
            continue
        capture_dir = study_dir / "captures" / row.get("capture_id", "")
        qc_path = capture_dir / "qc.json"
        if qc_path.exists():
            try:
                return json.loads(qc_path.read_text(encoding="utf-8"))["frame"]["mean_dn"]
            except (OSError, json.JSONDecodeError, KeyError):
                return None
    return None
