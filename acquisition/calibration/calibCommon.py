#!/usr/bin/env python3
"""Część wspólna narzędzi kalibracyjnych (spec-akwizycji.md §7).

Ujęcia kalibracyjne trafiają do `calib/<kind>_<id>/` i **nie są mieszane z materiałem
pomiarowym**. Powstają tą samą linią polecenia co ujęcia pomiarowe — kalibracja zrobiona
na innych parametrach ISP niż materiał nie opisuje tego samego toru i jest bezwartościowa.
Stąd import `build_command` z captureSample zamiast drugiej implementacji.

Żadne z tych narzędzi nie zapisuje wyniku do aktywnego profilu. Wypisują fragment do
wklejenia i wymagają nowego `profile_id`, bo zmiana wartości profilu w trakcie badania
unieważnia porównywalność zebranego materiału (§3, §12.6).
"""
from __future__ import annotations

import sys
from pathlib import Path

_ACQUISITION = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ACQUISITION / "capture"))
sys.path.insert(0, str(_ACQUISITION / "qc"))

import captureSample as acq          # noqa: E402  (po ustawieniu sys.path)
import imageStats as stats           # noqa: E402

AcquisitionError = acq.AcquisitionError


def setup(config_path: Path):
    """Konfiguracja, profil, weryfikacja strojenia, katalog badania."""
    station = acq.load_station(config_path)
    profile, profile_sha = acq.load_profile(station["profile_path"])
    tuning_sha = acq.verify_tuning_file(profile)
    station["archive_root"].mkdir(parents=True, exist_ok=True)
    study_dir = acq.ensure_study(station, profile, profile_sha)
    return station, profile, profile_sha, tuning_sha, study_dir


def new_calib_dir(study_dir: Path, kind: str) -> tuple[str, Path]:
    calib_id = f"{kind}_{acq.now_stamp()}"
    path = study_dir / "calib" / calib_id
    path.mkdir(parents=True)
    return calib_id, path


def capture_into(station: dict, profile: dict, directory: Path, name: str,
                 shutter_us: int | None = None) -> tuple[Path, dict, list]:
    """Jedno ujęcie kalibracyjne. `shutter_us` nadpisuje czas z profilu (drabinka §12.6)."""
    effective = dict(profile) if shutter_us is None else {**profile,
                                                          "shutter_us": shutter_us}
    image = directory / f"{name}.{profile['encoding']}"
    meta_path = directory / f"{name}_meta.json"
    command = acq.build_command(station, effective, image, meta_path)
    acq.run_capture(command)
    if not image.exists():
        raise AcquisitionError(f"rpicam-still nie zapisał obrazu: {image}")
    return image, acq.read_json(meta_path), command


def contract_violations(meta: dict, profile: dict, reference: dict,
                        shutter_us: int | None = None) -> list[str]:
    """Kontrakt §5 na ujęciu kalibracyjnym.

    Przy drabince czasów porównujemy z profilem o podmienionym `shutter_us`, więc czas
    jest sprawdzany wobec wartości **zadanej**, a nie wobec profilu. Reszta parametrów
    musi się zgadzać dokładnie tak samo jak przy materiale pomiarowym.
    """
    effective = dict(profile) if shutter_us is None else {**profile,
                                                          "shutter_us": shutter_us}
    checks, _ = acq.verify_contract(meta, effective, reference)
    if reference.get("reference_ccm") is None:
        reference["reference_ccm"] = meta.get("ColourCorrectionMatrix")
    return [f"{c['field']}: zmierzone {c['actual']}, oczekiwane {c['expected']}"
            for c in checks if c["status"] in ("naruszenie", "brak")]


def finish(study_dir: Path, kind: str, calib_id: str, directory: Path,
           payload: dict) -> None:
    """Zapis wyniku, sumy kontrolne katalogu i wpis do dziennika."""
    acq.write_json(directory / "calib.json", {"calib_id": calib_id, "kind": kind,
                                              "created_at": acq.now_iso(), **payload})
    acq.write_checksums(directory)
    acq.journal(study_dir, "calibration", {"kind": kind, "calib_id": calib_id,
                                           "path": str(directory)})


def print_profile_patch(field: str, value) -> None:
    print("\nDo profilu — jako nowy profile_id, nie nadpisanie aktywnego (§3):")
    print(f'  "{field}": {value!r}'.replace("'", '"'))
