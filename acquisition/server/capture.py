"""Prosta akwizycja: sesja → etykieta (podfolder) → seria zdjęć PNG+DNG.

Struktura na dysku:

    dane/
      sesja_YYYYMMDD_HHMM/
        BAD/   BAD_1.png  BAD_1.dng  BAD_2.png  BAD_2.dng …
        NICE/  NICE_1.png NICE_1.dng …
        .thumb/  BAD_1.jpg …          (miniatury do UI, kasowalne)

Parametry kamery są zamrożone z profilu (czas, wzmocnienia, AWB, plik strojenia,
ISP bez wyostrzania/denoise) — dokładnie jak w `photoSingle.py`. `--raw` sprawia,
że rpicam-still zapisuje DNG obok PNG (ten sam trzon nazwy).

Bez rpicam-still w systemie (maszyna dev) działa atrapa: syntetyczny PNG + placeholder
DNG, żeby cały przepływ dało się przeklikać bez Pi.
"""
from __future__ import annotations

import asyncio
import re
import shutil
from datetime import datetime
from pathlib import Path

from PIL import Image

from .config import Config

THUMB_LONG = 320
_SAFE = re.compile(r"[^A-Za-z0-9_-]+")

# Plik strojenia bywa w innym katalogu zależnie od modelu Pi — jak w photoSingle.py.
TUNING_CANDIDATES = [
    "/usr/share/libcamera/ipa/rpi/pisp/imx477_scientific.json",  # Pi 5
    "/usr/share/libcamera/ipa/rpi/vc4/imx477_scientific.json",   # Pi 4
]


def resolve_tuning(profile: dict) -> str | None:
    """Ścieżka z profilu, jeśli istnieje; inaczej wykryj (Pi5/Pi4); inaczej None.

    Wspólne dla zdjęcia i podglądu, żeby oba używały tego samego pliku strojenia."""
    configured = profile.get("tuning_file")
    if configured and Path(configured).exists():
        return configured
    for candidate in TUNING_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def sanitize_label(name: str) -> str:
    """Nazwa etykiety bezpieczna dla katalogu; spacje→_, reszta znaków→_."""
    cleaned = _SAFE.sub("_", (name or "").strip()).strip("_")
    if not cleaned:
        raise ValueError("Pusta nazwa etykiety.")
    return cleaned


class CaptureController:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.session_dir: Path | None = None
        self.label: str | None = None

    # ------------------------------------------------------------- sesja
    def start_session(self) -> dict:
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        name = f"sesja_{stamp}"
        path = self.config.data_root / name
        # gdyby dwie sesje w tej samej minucie — dołóż sufiks
        suffix = 1
        while path.exists():
            suffix += 1
            path = self.config.data_root / f"{name}_{suffix}"
        path.mkdir(parents=True, exist_ok=True)
        self.session_dir = path
        self.label = None
        return self.state()

    def set_label(self, name: str) -> dict:
        if self.session_dir is None:
            raise RuntimeError("Najpierw rozpocznij sesję.")
        label = sanitize_label(name)
        (self.session_dir / label).mkdir(exist_ok=True)
        self.label = label
        return self.state()

    # ------------------------------------------------------------- stan
    def _counts(self) -> dict:
        if self.session_dir is None:
            return {}
        out = {}
        for sub in sorted(self.session_dir.iterdir()):
            if sub.is_dir() and not sub.name.startswith("."):
                out[sub.name] = len(list(sub.glob("*.png")))
        return out

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
        }

    # ------------------------------------------------------------- zdjęcie
    async def shoot(self) -> dict:
        if self.session_dir is None or self.label is None:
            raise RuntimeError("Ustaw sesję i nazwę przed zdjęciem.")
        label = self.label
        index = self._next_index(label)
        stem = f"{label}_{index}"
        png = self.session_dir / label / f"{stem}.png"

        if self._use_dummy():
            await asyncio.get_event_loop().run_in_executor(None, _dummy_shot, png)
        else:
            await self._rpicam(png)

        dng = png.with_suffix(".dng")
        self._thumb(png)
        return {
            "label": label, "index": index,
            "png": png.name, "dng": dng.name if dng.exists() else None,
            "counts": self._counts(),
        }

    def _use_dummy(self) -> bool:
        return self.config.force_dummy or shutil.which(self.config.rpicam_still) is None

    def resolve_tuning(self) -> str | None:
        return resolve_tuning(self.config.profile)

    def diagnostics(self) -> dict:
        """Stan gotowości do zdjęcia — pokazywany w UI, żeby problem był widać z góry."""
        tuning = self.resolve_tuning()
        warnings = []
        if not self._use_dummy() and tuning is None:
            warnings.append("brak pliku strojenia scientific — zdjęcia w domyślnym tuningu")
        return {
            "dummy": self._use_dummy(),
            "rpicam_present": shutil.which(self.config.rpicam_still) is not None,
            "tuning_file": tuning,
            "warnings": warnings,
        }

    def _command(self, png: Path) -> list[str]:
        p = self.config.profile
        isp = p.get("isp", {})
        w, h = p["resolution"]
        red, blue = p["awb_gains"]
        cmd = [self.config.rpicam_still, "-o", str(png), "--encoding", "png",
               "--width", str(w), "--height", str(h),
               "--shutter", str(p["shutter_us"]), "--gain", str(p["analogue_gain"]),
               "--awbgains", f"{red},{blue}",
               "--sharpness", str(isp.get("sharpness", 0)),
               "--denoise", str(isp.get("denoise", "off")),
               "--saturation", str(isp.get("saturation", 1.0)),
               "--contrast", str(isp.get("contrast", 1.0)),
               "--brightness", str(isp.get("brightness", 0)),
               "--immediate", "--raw"]   # --raw → DNG obok PNG
        tuning = self.resolve_tuning()
        if tuning:
            cmd += ["--tuning-file", tuning]   # brak → domyślny tuning (jak photoSingle)
        return cmd

    async def _rpicam(self, png: Path) -> None:
        proc = await asyncio.create_subprocess_exec(
            *self._command(png), stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE)
        _, err = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"rpicam-still kod {proc.returncode}: "
                               f"{err.decode('utf-8', 'replace').strip()}")

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


def _dummy_shot(png: Path) -> None:
    """Atrapa: syntetyczny szary PNG + placeholder DNG (dev bez kamery)."""
    import numpy as np
    rng = np.random.default_rng()
    img = rng.integers(60, 190, size=(760, 1014, 3), dtype=np.uint8)
    Image.fromarray(img).save(png)
    png.with_suffix(".dng").write_bytes(b"DNG-PLACEHOLDER (dev)\n")
