"""Owijka na silnik `captureSample.py` (integracja subprocess-first).

Serwer **nie duplikuje** logiki kontraktu, sesji ani archiwum — woła CLI Michała
i czyta jego wyniki (`manifest.csv`, `capture.png`, `acquisition.json`). Dzięki
temu Faza 0/1 nie wymaga zmian w jego kodzie. Docelowo (do uzgodnienia) silnik
zostanie rozdzielony na część importowalną i CLI; wtedy zmieni się tylko wnętrze
tej klasy, nie API serwera.

Kontrakt (§5) liczy silnik i zapisuje `contract_status` do manifestu. QC (§6) jest
osobną bramką (patrz `qc.py`) — po zapisie serwer liczy QC z `capture.png` i dokłada
`qc.json` obok rekordu (poza sumami kontrolnymi, jak `derived/`).
"""
from __future__ import annotations

import asyncio
import csv
from dataclasses import dataclass
from pathlib import Path

from .config import Config

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REJECTED = 2


@dataclass
class EngineResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == EXIT_OK

    @property
    def rejected(self) -> bool:
        return self.exit_code == EXIT_REJECTED


class CaptureEngine:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._script = (Path(__file__).resolve().parent.parent
                        / "capture" / "captureSample.py")

    async def _run(self, *args: str) -> EngineResult:
        proc = await asyncio.create_subprocess_exec(
            "python3", str(self._script), "-c", str(self.config.station_path),
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await proc.communicate()
        return EngineResult(proc.returncode or 0,
                            out.decode("utf-8", "replace"),
                            err.decode("utf-8", "replace"))

    # --- operacje wystawiane serwerowi ---

    async def declare_sample(self, **fields) -> EngineResult:
        """§8: --batch/--sample/--supplier/--material/--verdict/--reasons/--stage/..."""
        args: list[str] = []
        for key, value in fields.items():
            if value is None or value == "":
                continue
            flag = f"--{key.replace('_', '-')}"
            if isinstance(value, bool):
                if value:            # store_true (np. --no-calibration) — bez wartości
                    args.append(flag)
                continue
            args += [flag, str(value)]
        return await self._run(*args)

    async def advance_layout(self) -> EngineResult:
        """§2: 'przesypałem materiał' — layout_seq += 1."""
        return await self._run("--layout")

    async def capture(self) -> EngineResult:
        """Wykonanie ujęcia (silnik: kontrakt §5 + archiwum §10). Bez QC (§6)."""
        return await self._run()

    async def end_session(self) -> EngineResult:
        return await self._run("--session-end")

    # --- odczyt wyników silnika ---

    def last_manifest_row(self) -> dict | None:
        """Ostatni wiersz manifest.csv — źródło capture_id i statusów (§10.1)."""
        manifest = self.config.study_dir / "manifest.csv"
        if not manifest.exists():
            return None
        with manifest.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        return rows[-1] if rows else None

    def capture_dir(self, capture_id: str) -> Path | None:
        """Katalog ujęcia — captures/ (zaakceptowane) lub rejected/."""
        for sub in ("captures", "rejected"):
            candidate = self.config.study_dir / sub / capture_id
            if candidate.exists():
                return candidate
        return None
