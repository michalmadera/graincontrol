"""Menedżer kamery — jeden komponent szeregujący podgląd i ujęcie (§12.9).

Kamera to zasób wyłączny: `rpicam-still` nie zrobi ujęcia, gdy strumień podglądu
trzyma urządzenie. Menedżer wymusza sekwencję *zatrzymanie podglądu → ujęcie →
wznowienie podglądu* pod jednym zamkiem. Żądanie ujęcia w trakcie przejścia jest
**odrzucane**, nie kolejkowane (§12.9).

Podgląd chodzi na parametrach profilu (NIE automatyka — §12.9): operator nie może
ustawiać sceny pod inny obraz, niż zostanie zapisany. Backend `rpicam-vid` na Pi,
`DummyBackend` do testów bez sprzętu.
"""
from __future__ import annotations

import asyncio
import shutil
import struct
from typing import AsyncIterator, Awaitable, Callable

JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"


class CameraError(RuntimeError):
    pass


class CameraBusy(CameraError):
    """Żądanie ujęcia w trakcie przełączania podglądu (§12.9) — odrzucane."""


# --------------------------------------------------------------------------- #
# Backendy urządzenia
# --------------------------------------------------------------------------- #

class DummyBackend:
    """Syntetyczny strumień JPEG — pozwala testować szeregowanie bez kamery."""

    def __init__(self, size=(640, 480)) -> None:
        self.size = size
        self._frame = _solid_jpeg(size)

    async def frames(self) -> AsyncIterator[bytes]:
        while True:
            yield self._frame
            await asyncio.sleep(0.2)   # ~5 fps


class RpicamBackend:
    """Podgląd MJPEG z `rpicam-vid` na parametrach profilu, w zredukowanej rozdz.

    Rozdzielczość podglądu jest niższa niż ujęcia, ale parametry ekspozycji/AWB są
    z profilu — obraz na podglądzie odpowiada temu, co zostanie zapisane."""

    def __init__(self, profile: dict, rpicam_vid: str = "rpicam-vid",
                 size=(1014, 760)) -> None:
        self.profile = profile
        self.rpicam_vid = rpicam_vid
        self.size = size
        self._proc: asyncio.subprocess.Process | None = None

    def _command(self) -> list[str]:
        cmd = [self.rpicam_vid, "-t", "0", "--codec", "mjpeg", "--nopreview",
               "--width", str(self.size[0]), "--height", str(self.size[1]),
               "--shutter", str(self.profile["shutter_us"]),
               "--gain", str(self.profile["analogue_gain"]),
               "--awbgains", ",".join(str(g) for g in self.profile["awb_gains"]),
               "--tuning-file", self.profile["tuning_file"], "-o", "-"]
        return cmd

    async def frames(self) -> AsyncIterator[bytes]:
        self._proc = await asyncio.create_subprocess_exec(
            *self._command(), stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL)
        buffer = b""
        try:
            while True:
                chunk = await self._proc.stdout.read(65536)
                if not chunk:
                    break
                buffer += chunk
                start = buffer.find(JPEG_SOI)
                end = buffer.find(JPEG_EOI, start + 2)
                while start != -1 and end != -1:
                    yield buffer[start:end + 2]
                    buffer = buffer[end + 2:]
                    start = buffer.find(JPEG_SOI)
                    end = buffer.find(JPEG_EOI, start + 2)
        finally:
            await self.close()

    async def close(self) -> None:
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self._proc.kill()
        self._proc = None


def make_backend(config):
    """rpicam-vid, jeśli jest w systemie; inaczej atrapa (dev/test bez Pi)."""
    if config.force_dummy:
        return DummyBackend()
    if shutil.which(config.rpicam_vid):
        return RpicamBackend(config.profile, config.rpicam_vid)
    return DummyBackend()


# --------------------------------------------------------------------------- #
# Szeregujący menedżer
# --------------------------------------------------------------------------- #

class CameraManager:
    """Stany: idle → preview ⇄ (transition → capturing → transition) → preview."""

    def __init__(self, backend) -> None:
        self._backend = backend
        self._lock = asyncio.Lock()          # zamek urządzenia
        self._resume = asyncio.Event()       # podniesiony, gdy podgląd może biec
        self._resume.set()
        self.state = "idle"

    def snapshot(self) -> dict:
        return {"state": self.state, "backend": type(self._backend).__name__}

    async def preview_stream(self) -> AsyncIterator[bytes]:
        """Ramki multipart MJPEG; wstrzymywany na czas ujęcia bez zrywania połączenia."""
        self.state = "preview" if self.state == "idle" else self.state
        async for frame in self._backend.frames():
            # gdy trwa ujęcie, przestajemy czytać z urządzenia, ale trzymamy połączenie
            await self._resume.wait()
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n"
                   b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                   + frame + b"\r\n")

    async def run_exclusive(
            self, work: Callable[[], Awaitable], on_state=None):
        """Uruchamia `work()` (ujęcie) na wyłączność: pauza podglądu → praca → wznowienie.

        Zwolnienie urządzenia następuje przez opuszczenie `_resume` i zamek — backend
        podglądu przestaje czytać ramki. Żądanie w trakcie przejścia → CameraBusy.
        """
        if self._lock.locked():
            raise CameraBusy("Kamera zajęta — trwa inne ujęcie lub przełączanie.")
        async with self._lock:
            prev_state = self.state
            self.state = "transition"
            if on_state:
                on_state(self.state)
            self._resume.clear()
            await asyncio.sleep(0.3)         # pozwól backendowi zwolnić urządzenie
            await self._close_preview_device()
            try:
                self.state = "capturing"
                if on_state:
                    on_state(self.state)
                return await work()
            finally:
                self.state = "transition"
                if on_state:
                    on_state(self.state)
                self._resume.set()
                self.state = "preview" if prev_state != "idle" else "idle"
                if on_state:
                    on_state(self.state)

    async def _close_preview_device(self) -> None:
        close = getattr(self._backend, "close", None)
        if close:
            await close()


def _solid_jpeg(size) -> bytes:
    """Minimalny, poprawny JPEG w jednolitym szarym — bez zależności od Pillow."""
    try:
        from PIL import Image
        import io
        img = Image.new("RGB", size, (90, 90, 96))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return buf.getvalue()
    except Exception:
        # awaryjnie: pusta ramka SOI/EOI (klient ją pominie)
        return JPEG_SOI + struct.pack(">H", 0) + JPEG_EOI
