"""Akwizycja: sesja → etykieta (podfolder) → seria zdjęć, **tym samym silnikiem co CLI**.

Zdjęcie powstaje linią polecenia z `captureSample.build_command`, a po zapisie
przechodzi kontrakt akwizycji z §5: `ExposureTime`, `AnalogueGain`, `ColourGains`
±1%, `DigitalGain` 1,000 ±0,01 i `ColourCorrectionMatrix` identyczna jak w pierwszym
ujęciu sesji. Ujęcie niezgodne z profilem trafia do `odrzucone/` i **nie zwiększa
numeru** — operator powtarza je, a numeracja zostaje ciągła.

Struktura na dysku:

    dane/
      sesja_YYYYMMDD_HHMM/
        manifest.csv                 jeden wiersz na ujęcie
        journal.jsonl                dziennik dopisywany, nigdy edytowany
        BAD/   BAD_1.png  BAD_1.dng  BAD_1_meta.json  BAD_1_acquisition.json
               BAD_1.sha256          ← marker kompletności, pisany na końcu
        odrzucone/BAD/ …             ujęcia odrzucone przez kontrakt, z przyczyną
        .thumb/  BAD_1.jpg …         miniatury do UI, kasowalne
        .tmp/                        katalog roboczy pojedynczego ujęcia

Zapis jest atomowy w tym sensie, że `*.sha256` powstaje jako ostatni: plik zdjęcia bez
towarzyszącego mu `.sha256` to zapis przerwany i przy starcie sesji trafia do
`odrzucone/`. Zanik zasilania nie zostawia ujęcia wyglądającego na kompletne (§11).

Bez rpicam-still w systemie działa atrapa: syntetyczny PNG, placeholder DNG i metadane
zgodne z profilem, żeby przepływ dało się przeklikać bez Pi. Takie ujęcia mają
`_dummy: true` w metadanych i w rekordzie — nigdy nie da się ich pomylić z materiałem.
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from PIL import Image

from . import engine
from .config import Config

THUMB_LONG = 320
_SAFE = re.compile(r"[^A-Za-z0-9_-]+")
MANIFEST_COLUMNS = ["capture_id", "session", "label", "index", "timestamp",
                    "profile_id", "contract_status", "dummy", "image_sha256"]


def resolve_tuning(profile: dict) -> str | None:
    """Plik strojenia **z profilu**, bez podmian.

    Wcześniejsza wersja przy braku pliku szukała wariantu Pi4/Pi5, a gdy nie znalazła
    żadnego — robiła zdjęcie na domyślnym `imx477.json`. To inna krzywa tonalna, inne
    macierze CCM i obecny blok ALSC: obraz wygląda poprawnie i jest nieporównywalny
    z resztą zbioru. Autowykrywanie należy do konfiguracji profilu, nie do momentu
    naciśnięcia migawki.
    """
    configured = profile.get("tuning_file")
    return configured if configured and Path(configured).exists() else None


def sanitize_label(name: str) -> str:
    """Nazwa etykiety bezpieczna dla katalogu; spacje→_, reszta znaków→_."""
    cleaned = _SAFE.sub("_", (name or "").strip()).strip("_")
    if not cleaned:
        raise ValueError("Pusta nazwa etykiety.")
    if cleaned == "odrzucone":
        raise ValueError("Nazwa 'odrzucone' jest zarezerwowana.")
    return cleaned


class CaptureController:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.session_dir: Path | None = None
        self.label: str | None = None
        self.session_id: str | None = None
        # odniesienia sesji: pierwsza macierz CCM i pierwszy Lux (§5)
        self.reference = {"reference_ccm": None, "reference_lux": None}
        self._tools: dict | None = None

    # ------------------------------------------------------------- sesja
    def start_session(self) -> dict:
        self._require_ready()
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        name = f"sesja_{stamp}"
        path = self.config.data_root / name
        suffix = 1
        while path.exists():
            suffix += 1
            path = self.config.data_root / f"{name}_{suffix}"
        path.mkdir(parents=True, exist_ok=True)
        (path / ".tmp").mkdir(exist_ok=True)
        self.session_dir = path
        self.session_id = path.name
        self.label = None
        self.reference = {"reference_ccm": None, "reference_lux": None}
        self._journal("session_start", {
            "profile_id": self.config.profile_id,
            "profile_sha256": self.config.profile_sha256,
            "tuning_file": self.config.profile.get("tuning_file"),
            "tuning_file_sha256": self.config.tuning_sha256,
            "dummy": self.config.dummy,
        })
        recovered = self._recover_interrupted()
        state = self.state()
        state["recovered"] = recovered
        return state

    def set_label(self, name: str) -> dict:
        if self.session_dir is None:
            raise RuntimeError("Najpierw rozpocznij sesję.")
        label = sanitize_label(name)
        (self.session_dir / label).mkdir(exist_ok=True)
        self.label = label
        self._journal("label_set", {"label": label})
        return self.state()

    def _recover_interrupted(self) -> list[str]:
        """Zapis przerwany zanikiem zasilania → odrzucone/, z przyczyną (§11)."""
        recovered = []
        staging_root = self.session_dir / ".tmp"
        for leftover in sorted(staging_root.iterdir()) if staging_root.exists() else []:
            if not leftover.is_dir():
                continue
            target = self.session_dir / "odrzucone" / "niedokonczone" / leftover.name
            target.parent.mkdir(parents=True, exist_ok=True)
            os.rename(leftover, target)
            self._journal("capture_recovered",
                          {"capture_id": leftover.name, "reason": "zapis niedokończony"})
            recovered.append(leftover.name)
        return recovered

    # ------------------------------------------------------------- stan
    def _counts(self) -> dict:
        if self.session_dir is None:
            return {}
        out = {}
        for sub in sorted(self.session_dir.iterdir()):
            if sub.is_dir() and not sub.name.startswith(".") and sub.name != "odrzucone":
                out[sub.name] = len(list(sub.glob("*.png")))
        return out

    def _rejected_count(self) -> int:
        rejected = self.session_dir / "odrzucone" if self.session_dir else None
        return len(list(rejected.rglob("*.png"))) if rejected and rejected.exists() else 0

    def _next_index(self, label: str) -> int:
        folder = self.session_dir / label
        highest = 0
        for png in folder.glob(f"{label}_*.png"):
            m = re.search(rf"{re.escape(label)}_(\d+)\.png$", png.name)
            if m:
                highest = max(highest, int(m.group(1)))
        return highest + 1

    def state(self) -> dict:
        return {
            "session": (self.session_dir.name if self.session_dir else None),
            "session_path": (str(self.session_dir) if self.session_dir else None),
            "label": self.label,
            "counts": self._counts(),
            "rejected": self._rejected_count(),
        }

    def diagnostics(self) -> dict:
        """Stan gotowości — pokazywany stale w UI, żeby blokada była widoczna (§12.12)."""
        tuning = resolve_tuning(self.config.profile)
        warnings = []
        if self.config.dummy:
            warnings.append("ATRAPA — zdjęcia syntetyczne, nie są materiałem pomiarowym")
        return {
            "dummy": self.config.dummy,
            "rpicam_present": shutil.which(self.config.rpicam_still) is not None,
            "profile_id": self.config.profile_id,
            "profile_sha256": self.config.profile_sha256,
            "tuning_file": tuning,
            "tuning_file_sha256": self.config.tuning_sha256,
            "shutter_us": self.config.profile.get("shutter_us"),
            "blocked": self.config.blocking_error,
            "warnings": warnings,
        }

    def _require_ready(self) -> None:
        if self.config.blocking_error:
            raise RuntimeError(self.config.blocking_error)

    # ------------------------------------------------------------- zdjęcie
    async def shoot(self) -> dict:
        self._require_ready()
        if self.session_dir is None or self.label is None:
            raise RuntimeError("Ustaw sesję i nazwę przed zdjęciem.")

        label = self.label
        index = self._next_index(label)      # numer rośnie dopiero po przyjęciu (§5)
        stem = f"{label}_{index}"
        staging = self.session_dir / ".tmp" / stem
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)

        png = staging / f"{stem}.png"
        meta_path = staging / f"{stem}_meta.json"
        command = engine.build_command(
            {"rpicam_still": self.config.rpicam_still}, self.config.profile,
            png, meta_path)

        loop = asyncio.get_event_loop()
        if self.config.dummy:
            await loop.run_in_executor(None, _dummy_shot, png, meta_path,
                                       self.config.profile)
        else:
            await self._rpicam(command)

        # Reszta jest synchroniczna i policzalna (sumy kontrolne ~40 MB), więc idzie
        # do wątku roboczego — inaczej API i podgląd zamierają na czas zapisu (§12.13).
        return await loop.run_in_executor(
            None, self._finish, staging, stem, label, index, command)

    def _finish(self, staging: Path, stem: str, label: str, index: int,
                command: list) -> dict:
        png = staging / f"{stem}.png"
        meta_path = staging / f"{stem}_meta.json"
        if not png.exists():
            raise RuntimeError(f"rpicam-still nie zapisał obrazu: {png.name}")
        try:
            raw_meta = engine.read_json(meta_path)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Nie da się odczytać metadanych ujęcia ({exc}). Zdjęcie "
                "z niezweryfikowanymi parametrami jest gorsze niż brak zdjęcia.")

        checks, warnings = engine.verify_contract(raw_meta, self.config.profile,
                                                  self.reference)
        violations = [c for c in checks if c["status"] in ("naruszenie", "brak")]
        accepted = not violations

        session_like = {"tools": self._tool_versions()}
        enriched = engine.enrich_meta(raw_meta, self.config.profile,
                                      self.config.profile_sha256,
                                      self.config.tuning_sha256, session_like, command)
        if self.config.dummy:
            enriched["_dummy"] = True
        engine.write_json(meta_path, enriched)

        timestamp = engine.now_iso()
        record = {
            "capture_id": stem, "session": self.session_id, "label": label,
            "index": index, "timestamp": timestamp,
            "profile_id": self.config.profile_id,
            "profile_sha256": self.config.profile_sha256,
            "tuning_file_sha256": self.config.tuning_sha256,
            "dummy": self.config.dummy,
            "qc": {"status": "not_run", "reason": "QC §6 nieobjęte tym narzędziem"},
            "contract": {"status": "ok" if accepted else "rejected",
                         "checks": checks, "warnings": warnings},
            "command_line": command,
            "tools": session_like["tools"],
        }
        engine.write_json(staging / f"{stem}_acquisition.json", record)

        sums = {p.name: engine.sha256_file(p) for p in sorted(staging.iterdir())}
        for name, digest in sums.items():                    # kontrola po zapisie (§11)
            if engine.sha256_file(staging / name) != digest:
                raise RuntimeError(f"Suma kontrolna {name} nie zgadza się po zapisie.")

        target = (self.session_dir / label if accepted
                  else self.session_dir / "odrzucone" / label)
        target.mkdir(parents=True, exist_ok=True)
        marker = f"{stem}.sha256"
        for name in sorted(sums):                            # marker na końcu
            os.replace(staging / name, target / name)
        (target / marker).write_text(
            "\n".join(f"{d}  {n}" for n, d in sorted(sums.items())) + "\n",
            encoding="utf-8")
        engine.fsync_dir(target)
        shutil.rmtree(staging, ignore_errors=True)

        if accepted:
            if self.reference["reference_ccm"] is None:
                self.reference["reference_ccm"] = raw_meta.get("ColourCorrectionMatrix")
            if self.reference["reference_lux"] is None:
                self.reference["reference_lux"] = raw_meta.get("Lux")
            self._thumb(target / f"{stem}.png")

        self._manifest({
            "capture_id": stem, "session": self.session_id, "label": label,
            "index": index, "timestamp": timestamp,
            "profile_id": self.config.profile_id,
            "contract_status": record["contract"]["status"],
            "dummy": self.config.dummy,
            "image_sha256": sums.get(f"{stem}.png"),
        })
        self._journal("capture_accepted" if accepted else "capture_rejected", {
            "capture_id": stem, "label": label, "index": index,
            "path": str(target / f"{stem}.png"),
            "violations": [f"{c['field']}: zmierzone {c['actual']}, "
                           f"oczekiwane {c['expected']}" for c in violations],
            "warnings": warnings,
        })

        dng = target / f"{stem}.dng"
        return {
            "label": label, "index": index, "accepted": accepted,
            "png": f"{stem}.png", "dng": dng.name if dng.exists() else None,
            "contract": record["contract"]["status"],
            "violations": [f"{c['field']}: zmierzone {c['actual']}, "
                           f"profil {c['expected']}" for c in violations],
            "warnings": warnings,
            "counts": self._counts(), "rejected": self._rejected_count(),
            "dummy": self.config.dummy,
        }

    def _tool_versions(self) -> dict:
        if self._tools is None:
            if self.config.dummy:
                self._tools = {"rpicam": "atrapa (brak rpicam-still)", "libcamera": None}
            else:
                self._tools = engine.tool_versions(self.config.rpicam_still)
        return self._tools

    async def _rpicam(self, command: list[str]) -> None:
        proc = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE)
        _, err = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"rpicam-still kod {proc.returncode}: "
                               f"{err.decode('utf-8', 'replace').strip()}")

    # ------------------------------------------------------------- zapisy pomocnicze
    def _manifest(self, row: dict) -> None:
        path = self.session_dir / "manifest.csv"
        exists = path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
            if not exists:
                writer.writeheader()
            writer.writerow(row)
            f.flush()
            os.fsync(f.fileno())

    def _journal(self, event: str, payload: dict) -> None:
        if self.session_dir is None:
            return
        with (self.session_dir / "journal.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": engine.now_iso(), "event": event, **payload},
                               ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _thumb(self, png: Path) -> None:
        try:
            thumb_dir = self.session_dir / ".thumb"
            thumb_dir.mkdir(exist_ok=True)
            with Image.open(png) as im:
                im = im.convert("RGB")
                scale = THUMB_LONG / max(im.size)
                if scale < 1.0:
                    im = im.resize((round(im.size[0] * scale), round(im.size[1] * scale)))
                im.save(thumb_dir / (png.stem + ".jpg"), quality=80)
        except Exception:
            pass  # miniatura to wygoda, nie może wywalić zapisu

    def thumb_path(self, label: str, index: int) -> Path | None:
        if self.session_dir is None:
            return None
        p = self.session_dir / ".thumb" / f"{sanitize_label(label)}_{index}.jpg"
        return p if p.exists() else None


def _dummy_shot(png: Path, meta_path: Path, profile: dict) -> None:
    """Atrapa: syntetyczny PNG, placeholder DNG i metadane zgodne z profilem.

    Metadane muszą przechodzić kontrakt, inaczej dev nie przetestuje ścieżki przyjęcia
    ujęcia. Znacznik `_dummy` w metadanych zapewnia, że takie zdjęcie nie zostanie
    później wzięte za materiał pomiarowy.
    """
    import numpy as np
    rng = np.random.default_rng()
    img = rng.integers(60, 190, size=(760, 1014, 3), dtype=np.uint8)
    Image.fromarray(img).save(png)
    png.with_suffix(".dng").write_bytes(b"DNG-PLACEHOLDER (dev)\n")
    red, blue = profile["awb_gains"]
    meta_path.write_text(json.dumps({
        "ExposureTime": profile["shutter_us"],
        "AnalogueGain": float(profile["analogue_gain"]),
        "DigitalGain": 1.0,
        "ColourGains": [float(red), float(blue)],
        "ColourCorrectionMatrix": [1.8, -0.6, -0.2, -0.3, 1.6, -0.3, 0.1, -0.7, 1.6],
        "Lux": 400.0,
        "_dummy": True,
    }), encoding="utf-8")
