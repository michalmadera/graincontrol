#!/usr/bin/env python3
"""Akwizycja jednej próbki — jedno ujęcie na wywołanie, wg docs/spec-akwizycji.md.

Program ma **uniemożliwić** zebranie danych, których później nie da się porównać (§0).
Stąd: parametry wyłącznie z profilu (§3), kontrakt akwizycji sprawdzany po każdym ujęciu
(§5), archiwum niezmienne i zapisywane atomowo (§10, §11). Ujęcie niezgodne z profilem
trafia do `rejected/`, nie do zbioru pomiarowego, i **nie** inkrementuje `frame_seq`.

Zakres tego pliku:

  zrobione   §2 identyfikatory i liczniki, §3 profil z sumami kontrolnymi,
             §5 kontrakt akwizycji, §8 metadane operatora, §9 (A i E),
             §10 format zapisu, §11 integralność i wznowienie
  poza       §6 QC na miejscu (max_dn, wzorce, ostrość) i `qc.json`,
             §7 kreatory kalibracji, §12 interfejs webowy, kopia zapasowa

Dopóki nie ma QC, dwa kryteria odbioru z §14 pozostają niespełnione: wykrycie
zasłoniętego wzorca i wykrycie rozjechanej ostrości. Program nie otwiera obrazu.

Użycie:

    captureSample.py -c station.json --batch D-2026-041 --sample S-017 \
        --supplier "Dostawca X" --material kruszywo-0-2 \
        --verdict NOK --reasons kremowy,zabrudzony --verdict-author JK --stage E
                                        # deklaracja próbki, bez zdjęcia
    captureSample.py -c station.json    # ujęcie: frame_seq += 1
    captureSample.py -c station.json --layout       # przesypano: layout_seq += 1
    captureSample.py -c station.json --session-end  # podsumowanie sesji

Kody wyjścia: 0 zapisane, 2 odrzucone przez kontrakt, 1 błąd.
Testy bez kamery: w `station.json` wskaż w `rpicam_still` atrapę zamiast rpicam-still.
Zależności: wyłącznie biblioteka standardowa.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REJECTED = 2

CAPTURE_TIMEOUT_S = 120
MANIFEST_COLUMNS = [
    "capture_id", "study_id", "batch_id", "sample_id", "layout_seq", "frame_seq",
    "session_id", "profile_id", "timestamp", "expert_verdict", "protocol_stage",
    "contract_status", "qc_status", "image_sha256",
]


class AcquisitionError(Exception):
    """Warunek, przy którym ujęcia nie wolno wykonać albo zapisać jako ważne."""


# --------------------------------------------------------------------------- #
# Narzędzia
# --------------------------------------------------------------------------- #

def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict) -> None:
    """Zapis atomowy — plik stanu nigdy nie zostaje uszkodzony przy zaniku zasilania."""
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    fsync_dir(path.parent)


def fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def require(mapping: dict, key: str, where: str):
    if key not in mapping:
        raise AcquisitionError(f"{where}: brak wymaganego pola '{key}'")
    return mapping[key]


def slug(value: str) -> str:
    """Postać bezpieczna dla nazwy katalogu. Wartość surowa zostaje w acquisition.json.

    §8 wymaga, by identyfikatory przyjmowały dowolny łańcuch i nie były walidowane poza
    niepustością — walidujemy więc tylko ścieżkę, a nie treść.
    """
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")


def journal(study_dir: Path, event: str, payload: dict) -> None:
    """Dziennik dopisywany, nigdy nie edytowany (§10)."""
    record = {"ts": now_iso(), "event": event, **payload}
    with (study_dir / "journal.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


# --------------------------------------------------------------------------- #
# Konfiguracja stanowiska i profil akwizycji
# --------------------------------------------------------------------------- #

def load_station(path: Path) -> dict:
    if not path.exists():
        raise AcquisitionError(f"Brak pliku konfiguracji stanowiska: {path}")
    station = read_json(path)
    for key in ("archive_root", "profile_path", "rpicam_still", "operator",
                "min_free_captures", "bytes_per_capture", "study"):
        require(station, key, str(path))
    study = station["study"]
    for key in ("study_id", "verdict_reasons_vocabulary", "protocol_stages",
                "verdicts"):
        require(study, key, f"{path} -> study")

    base = path.parent
    station["_path"] = str(path)
    station["archive_root"] = resolve_path(station["archive_root"], base)
    station["profile_path"] = resolve_path(station["profile_path"], base)
    return station


def resolve_path(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def load_profile(path: Path) -> tuple[dict, str]:
    """Profil §3 + jego suma kontrolna. Profil jest częścią tożsamości każdego zdjęcia."""
    if not path.exists():
        raise AcquisitionError(f"Brak pliku profilu akwizycji: {path}")
    profile = read_json(path)
    for key in ("profile_id", "resolution", "shutter_us", "analogue_gain", "awb_gains",
                "tuning_file", "tuning_file_sha256", "isp", "encoding", "raw",
                "immediate", "calibration", "contract"):
        require(profile, key, str(path))
    for key in ("sharpness", "denoise", "saturation", "contrast", "brightness"):
        require(profile["isp"], key, f"{path} -> isp")
    for key in ("exposure_rel", "analogue_gain_rel", "colour_gains_rel",
                "digital_gain_abs", "ccm_abs", "lux_warn_rel"):
        require(profile["contract"], key, f"{path} -> contract")
    return profile, sha256_file(path)


def verify_tuning_file(profile: dict) -> str:
    """Plik strojenia jest podmieniany przy aktualizacji libcamera pod tą samą nazwą.

    Zmiana strojenia unieważnia porównywalność bez żadnego widocznego sygnału (§3),
    więc rozbieżność sumy kontrolnej blokuje ujęcie, a nie ostrzega.
    """
    tuning = Path(profile["tuning_file"])
    if not tuning.exists():
        raise AcquisitionError(
            f"Brak pliku strojenia z profilu: {tuning}\n"
            "  Bez niego rpicam-still użyłby domyślnego imx477.json — inna krzywa\n"
            "  tonalna, inne macierze CCM i obecny blok ALSC. Obraz wyglądałby\n"
            "  poprawnie i byłby nieporównywalny z resztą zbioru.\n"
            "  Na Pi 5 ścieżka to .../ipa/rpi/pisp/, na Pi 4 .../ipa/rpi/vc4/."
        )
    actual = sha256_file(tuning)
    expected = profile["tuning_file_sha256"]
    if not expected:
        raise AcquisitionError(
            f"Profil nie ma sumy kontrolnej pliku strojenia. Zmierzona wartość:\n"
            f'  "tuning_file_sha256": "{actual}"\n'
            "  Wpisz ją do profilu — dopiero wtedy podmiana pliku przy aktualizacji\n"
            "  pakietu libcamera zostanie wykryta."
        )
    if actual != expected:
        raise AcquisitionError(
            f"Plik strojenia {tuning} ma inną sumę kontrolną niż profil.\n"
            f"  profil:    {expected}\n"
            f"  na dysku:  {actual}\n"
            "  Prawdopodobna aktualizacja libcamera. Materiał zebrany po tej zmianie\n"
            "  nie jest porównywalny z wcześniejszym — wymagany nowy profile_id."
        )
    return actual


def tool_versions(rpicam: str) -> dict:
    try:
        out = subprocess.run([rpicam, "--version"], capture_output=True, text=True,
                             timeout=30).stdout
    except FileNotFoundError:
        raise AcquisitionError(f"Nie znaleziono '{rpicam}' — zainstaluj rpicam-apps.")
    versions = {"rpicam": None, "libcamera": None}
    for line in out.splitlines():
        low = line.lower()
        if "libcamera" in low:
            versions["libcamera"] = line.strip()
        elif versions["rpicam"] is None and line.strip():
            versions["rpicam"] = line.strip()
    return versions


# --------------------------------------------------------------------------- #
# Badanie i sesja
# --------------------------------------------------------------------------- #

def ensure_study(station: dict, profile: dict, profile_sha: str) -> Path:
    """Katalog badania. Profil jest niezmienny w obrębie study_id (§3)."""
    study_id = station["study"]["study_id"]
    study_dir = station["archive_root"] / study_id
    (study_dir / "captures").mkdir(parents=True, exist_ok=True)
    (study_dir / "rejected").mkdir(exist_ok=True)
    (study_dir / "calib").mkdir(exist_ok=True)
    (study_dir / "sessions").mkdir(exist_ok=True)
    (study_dir / ".tmp").mkdir(exist_ok=True)

    study_file = study_dir / "study.json"
    if not study_file.exists():
        write_json(study_file, {"created_at": now_iso(), **station["study"]})
        journal(study_dir, "study_created", {"study_id": study_id})

    profile_file = study_dir / "profile.json"
    if not profile_file.exists():
        write_json(profile_file, profile)
        journal(study_dir, "profile_frozen",
                {"profile_id": profile["profile_id"], "profile_sha256": profile_sha})
    else:
        frozen = read_json(profile_file)
        if frozen != profile:
            differences = [f"    {key}: zamrożone {frozen.get(key)!r}, "
                           f"podane {profile.get(key)!r}"
                           for key in sorted(set(frozen) | set(profile))
                           if frozen.get(key) != profile.get(key)]
            raise AcquisitionError(
                f"Profil różni się od zamrożonego w badaniu {study_id}:\n"
                + "\n".join(differences) + "\n"
                "  Każda zmiana wartości wymaga nowego profile_id i jawnej decyzji:\n"
                "  nowe badanie albo świadome rozgałęzienie (§3)."
            )
    return study_dir


def recover_interrupted(study_dir: Path) -> list[str]:
    """Katalog tymczasowy po zaniku zasilania → rejected/, z przyczyną (§11, §12.12)."""
    recovered = []
    for leftover in sorted((study_dir / ".tmp").iterdir()):
        if not leftover.is_dir():
            continue
        target = study_dir / "rejected" / f"{leftover.name}_niedokonczony"
        if target.exists():
            target = target.with_name(target.name + "_" + now_stamp())
        os.rename(leftover, target)
        journal(study_dir, "capture_recovered",
                {"capture_id": leftover.name, "reason": "zapis niedokończony"})
        recovered.append(leftover.name)
    return recovered


def session_path(study_dir: Path) -> Path:
    return study_dir / "session.json"


def load_session(study_dir: Path) -> dict | None:
    path = session_path(study_dir)
    return read_json(path) if path.exists() else None


def start_session(study_dir: Path, station: dict, profile: dict, profile_sha: str,
                  tuning_sha: str, args) -> dict:
    session = {
        "session_id": datetime.now().strftime("%Y%m%d-%H%M"),
        "started_at": now_iso(),
        "study_id": station["study"]["study_id"],
        "profile_id": profile["profile_id"],
        "profile_sha256": profile_sha,
        "tuning_file_sha256": tuning_sha,
        "operator": args.operator or station["operator"],
        "illuminator_id": station.get("illuminator_id"),
        "illuminator_on_since": args.illuminator_on_since,
        "temperature_c": args.temperature,
        "notes": args.session_notes,
        "tools": tool_versions(station["rpicam_still"]),
        "no_calibration": bool(args.no_calibration),
        "reference_ccm": None,
        "reference_lux": None,
        "last_lux": None,
        "sample": None,
        "counts": {"accepted": 0, "rejected": 0},
        "samples_seen": [],
    }
    write_json(session_path(study_dir), session)
    journal(study_dir, "session_start", {k: session[k] for k in
                                         ("session_id", "operator", "profile_id",
                                          "no_calibration")})
    return session


def verify_session_profile(session: dict, profile: dict, profile_sha: str,
                           tuning_sha: str) -> None:
    if session["profile_sha256"] != profile_sha:
        raise AcquisitionError(
            "Profil zmienił się w trakcie sesji — zamknij sesję (--session-end)\n"
            "  i rozstrzygnij, czy to nowe badanie (§3)."
        )
    if session["tuning_file_sha256"] != tuning_sha:
        raise AcquisitionError(
            "Plik strojenia zmienił się w trakcie sesji. Ujęcia z tej sesji nie są\n"
            "  wzajemnie porównywalne — zamknij sesję i zbadaj przyczynę."
        )


def check_calibration(study_dir: Path, profile: dict, session: dict,
                      acknowledged: bool) -> None:
    """Bez flat-fielda i skali program odmawia startu sesji pomiarowej (§7)."""
    if acknowledged and not session["no_calibration"]:
        session["no_calibration"] = True
        write_json(session_path(study_dir), session)
        journal(study_dir, "calibration_waived", {"session_id": session["session_id"]})
    calib = profile["calibration"]
    missing = [k for k in ("flatfield_id", "scale_id") if not calib.get(k)]
    if missing and not session["no_calibration"]:
        raise AcquisitionError(
            f"Profil nie ma ważnej kalibracji: {', '.join(missing)}.\n"
            "  Plik strojenia scientific nie zawiera bloku ALSC, więc flat-field jest\n"
            "  obowiązkowy, a skala mm/px bez wzorca jest założeniem, nie pomiarem.\n"
            "  Świadome pominięcie: --no-calibration (flaga trafia do każdego rekordu)."
        )


def check_disk(station: dict) -> None:
    budget = station["min_free_captures"] * station["bytes_per_capture"]
    free = shutil.disk_usage(station["archive_root"]).free
    if free < budget:
        raise AcquisitionError(
            f"Za mało miejsca na dysku: {free / 1e9:.1f} GB, wymagane "
            f"{budget / 1e9:.1f} GB ({station['min_free_captures']} ujęć)."
        )


# --------------------------------------------------------------------------- #
# Deklaracja próbki (§8) i liczniki (§2)
# --------------------------------------------------------------------------- #

def declare_sample(study_dir: Path, session: dict, study: dict, args) -> dict:
    missing = [name for name, value in (
        ("--batch", args.batch), ("--sample", args.sample),
        ("--supplier", args.supplier), ("--material", args.material),
        ("--verdict", args.verdict), ("--verdict-author", args.verdict_author),
        ("--stage", args.stage)) if not value]
    if missing:
        raise AcquisitionError("Deklaracja próbki wymaga: " + ", ".join(missing))

    if args.verdict not in study["verdicts"]:
        raise AcquisitionError(
            f"Werdykt '{args.verdict}' spoza słownika: {', '.join(study['verdicts'])}")
    if args.stage not in study["protocol_stages"]:
        raise AcquisitionError(
            f"Etap '{args.stage}' spoza listy: {', '.join(study['protocol_stages'])}")

    reasons = [r.strip() for r in (args.reasons or "").split(",") if r.strip()]
    unknown = [r for r in reasons if r not in study["verdict_reasons_vocabulary"]]
    if unknown:
        raise AcquisitionError(
            f"Przyczyny spoza słownika kontrolowanego: {', '.join(unknown)}\n"
            f"  dozwolone: {', '.join(study['verdict_reasons_vocabulary'])}\n"
            "  Przyczyny są zmienną objaśnianą przy dobieraniu progów — wpisane\n"
            "  swobodnie nie dadzą się zagregować (§8)."
        )

    # §9: etapy D i E mają wymuszony werdykt, E dodatkowo niepustą listę przyczyn.
    if args.stage == "D" and args.verdict != "OK":
        raise AcquisitionError("Etap D zbiera materiał akceptowany — wymagany werdykt OK.")
    if args.stage == "E":
        if args.verdict not in ("NOK", "graniczny"):
            raise AcquisitionError(
                "Etap E zbiera materiał odrzucany — werdykt NOK albo graniczny.")
        if not reasons:
            raise AcquisitionError("Etap E wymaga niepustej listy --reasons.")

    sample = {
        "batch_id": args.batch,
        "sample_id": args.sample,
        "supplier": args.supplier,
        "material_type": args.material,
        "expert_verdict": args.verdict,
        "verdict_reasons": reasons,
        "verdict_author": args.verdict_author,
        "verdict_date": args.verdict_date or datetime.now().strftime("%Y-%m-%d"),
        "protocol_stage": args.stage,
        "notes": args.notes,
        "declared_at": now_iso(),
        "layout_seq": 1,
        "frame_seq": 0,
    }
    session["sample"] = sample
    key = f"{args.batch}/{args.sample}"
    if key not in session["samples_seen"]:
        session["samples_seen"].append(key)
    write_json(session_path(study_dir), session)
    journal(study_dir, "sample_declared", {"session_id": session["session_id"], **sample})
    return sample


def advance_layout(study_dir: Path, session: dict) -> dict:
    sample = session.get("sample")
    if not sample:
        raise AcquisitionError("Najpierw zadeklaruj próbkę (--batch/--sample/…).")
    if sample["protocol_stage"] == "A":
        raise AcquisitionError(
            "Etap A bada powtarzalność samego ujęcia — przesypanie jest zablokowane (§9).")
    sample["layout_seq"] += 1
    sample["frame_seq"] = 0
    write_json(session_path(study_dir), session)
    journal(study_dir, "layout_advance",
            {"session_id": session["session_id"], "batch_id": sample["batch_id"],
             "sample_id": sample["sample_id"], "layout_seq": sample["layout_seq"]})
    return sample


# --------------------------------------------------------------------------- #
# Ujęcie i kontrakt akwizycji (§5)
# --------------------------------------------------------------------------- #

def build_command(station: dict, profile: dict, image: Path, meta: Path) -> list[str]:
    isp = profile["isp"]
    width, height = profile["resolution"]
    red, blue = profile["awb_gains"]
    command = [
        station["rpicam_still"],
        "-o", str(image),
        "--encoding", profile["encoding"],
        "--width", str(width), "--height", str(height),
        "--tuning-file", profile["tuning_file"],
        # ręczna ekspozycja -> AEC/AGC off; --awbgains samo wyłącza AWB
        "--shutter", str(profile["shutter_us"]),
        "--gain", str(profile["analogue_gain"]),
        "--awbgains", f"{red},{blue}",
        # ISP: bez wyostrzania i denoise, tony i chroma zamrożone
        "--sharpness", str(isp["sharpness"]),
        "--denoise", str(isp["denoise"]),
        "--saturation", str(isp["saturation"]),
        "--contrast", str(isp["contrast"]),
        "--brightness", str(isp["brightness"]),
        "--metadata", str(meta), "--metadata-format", "json",
    ]
    if profile["immediate"]:
        command.append("--immediate")
    if profile["raw"]:
        command.append("--raw")  # DNG przed ISP — jedyna droga odwrotu (rekomendacja §5)
    return command


def run_capture(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True, timeout=CAPTURE_TIMEOUT_S)
    except FileNotFoundError:
        raise AcquisitionError(f"Nie znaleziono '{command[0]}' — zainstaluj rpicam-apps.")
    except subprocess.TimeoutExpired:
        raise AcquisitionError("rpicam-still nie zakończył się w czasie — kamera zajęta?")
    except subprocess.CalledProcessError as exc:
        raise AcquisitionError(f"rpicam-still zakończył się kodem {exc.returncode}.")


def check_scalar(name, actual, expected, rel=None, abs_=None) -> dict:
    result = {"field": name, "expected": expected, "actual": actual, "status": "ok"}
    if actual is None:
        result.update(status="brak", detail="pole nieobecne w metadanych")
        return result
    limit = abs_ if abs_ is not None else abs(expected) * rel
    result["tolerance"] = limit
    if abs(actual - expected) > limit:
        result["status"] = "naruszenie"
    return result


def verify_contract(meta: dict, profile: dict, session: dict) -> tuple[list, list]:
    """Porównanie metadanych rpicam-still z profilem. Brak pola = naruszenie (§0)."""
    tol = profile["contract"]
    checks = [
        check_scalar("ExposureTime", meta.get("ExposureTime"), profile["shutter_us"],
                     rel=tol["exposure_rel"]),
        check_scalar("AnalogueGain", meta.get("AnalogueGain"), profile["analogue_gain"],
                     rel=tol["analogue_gain_rel"]),
        check_scalar("DigitalGain", meta.get("DigitalGain"), 1.0,
                     abs_=tol["digital_gain_abs"]),
    ]

    gains = meta.get("ColourGains")
    if gains is None or len(gains) != 2:
        checks.append({"field": "ColourGains", "expected": profile["awb_gains"],
                       "actual": gains, "status": "brak"})
    else:
        for index, label in ((0, "R"), (1, "B")):
            checks.append(check_scalar(f"ColourGains[{label}]", gains[index],
                                       profile["awb_gains"][index],
                                       rel=tol["colour_gains_rel"]))

    # CCM: plik strojenia wybiera macierz wg oszacowanej temperatury barwowej. Przy
    # zamrożonych awbgains powinno być to deterministyczne — sprawdzamy, nie zakładamy.
    ccm = meta.get("ColourCorrectionMatrix")
    reference = session.get("reference_ccm")
    if ccm is None:
        checks.append({"field": "ColourCorrectionMatrix", "expected": reference,
                       "actual": None, "status": "brak"})
    elif reference is None:
        checks.append({"field": "ColourCorrectionMatrix", "expected": None,
                       "actual": ccm, "status": "odniesienie",
                       "detail": "pierwsze ujęcie sesji — macierz staje się odniesieniem"})
    else:
        deviation = max(abs(a - b) for a, b in zip(ccm, reference))
        checks.append({"field": "ColourCorrectionMatrix", "expected": reference,
                       "actual": ccm, "tolerance": tol["ccm_abs"],
                       "status": "ok" if deviation <= tol["ccm_abs"] else "naruszenie",
                       "max_abs_diff": deviation})

    warnings = []
    lux = meta.get("Lux")
    if lux is not None and session.get("reference_lux"):
        change = abs(lux - session["reference_lux"]) / session["reference_lux"]
        if change > tol["lux_warn_rel"]:
            warnings.append(
                f"Lux {lux:.1f} różni się o {change * 100:.1f}% od pierwszego ujęcia "
                f"sesji ({session['reference_lux']:.1f}) — sprawdź oświetlacz.")
    return checks, warnings


# --------------------------------------------------------------------------- #
# Zapis archiwum (§10, §11)
# --------------------------------------------------------------------------- #

def enrich_meta(meta: dict, profile: dict, profile_sha: str, tuning_sha: str,
                session: dict, command: list[str]) -> dict:
    """Pola, których kamera nie raportuje, a których wymaga warstwa pomiarowa (§10)."""
    isp = profile["isp"]
    return {
        **meta,
        "_isp_sharpness": isp["sharpness"],
        "_isp_denoise": isp["denoise"],
        "_isp_saturation": isp["saturation"],
        "_isp_contrast": isp["contrast"],
        "_isp_brightness": isp["brightness"],
        "_tuning_file": profile["tuning_file"],
        "_tuning_file_sha256": tuning_sha,
        "_rpicam_version": session["tools"]["rpicam"],
        "_libcamera_version": session["tools"]["libcamera"],
        "_profile_id": profile["profile_id"],
        "_profile_sha256": profile_sha,
        "_command_line": command,
    }


def write_checksums(directory: Path) -> dict:
    sums = {}
    lines = []
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.name != "sha256sums.txt":
            digest = sha256_file(path)
            sums[path.name] = digest
            lines.append(f"{digest}  {path.name}")
    (directory / "sha256sums.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sums


def verify_checksums(directory: Path, expected: dict) -> None:
    """Sumy liczone po zapisie, przed potwierdzeniem dla operatora (§11)."""
    for name, digest in expected.items():
        if sha256_file(directory / name) != digest:
            raise AcquisitionError(
                f"Suma kontrolna {name} nie zgadza się po zapisie — nośnik uszkodzony?")


def append_manifest(study_dir: Path, row: dict) -> None:
    path = study_dir / "manifest.csv"
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)
        f.flush()
        os.fsync(f.fileno())


def allocate_capture_id(study_dir: Path, session: dict, sample: dict, frame: int) -> str:
    """Identyfikator wg §2, z gwarancją unikalności.

    Odrzucenie nie inkrementuje `frame_seq`, więc powtórka ujęcia po odrzuceniu ma te
    same liczniki i różni ją wyłącznie znacznik czasu o rozdzielczości sekundy. Czekamy
    na kolejną sekundę zamiast dopisywać sufiks — format identyfikatora jest częścią
    specyfikacji, a nazwa katalogu nigdy nie może trafić na istniejącą.
    """
    prefix = (f"{slug(session['study_id'])}_{slug(sample['batch_id'])}"
              f"_{slug(sample['sample_id'])}"
              f"_L{sample['layout_seq']:02d}F{frame:02d}")
    for _ in range(5):
        capture_id = f"{prefix}_{now_stamp()}"
        if not any((study_dir / sub / capture_id).exists()
                   for sub in ("captures", "rejected", ".tmp")):
            return capture_id
        time.sleep(1.0)
    raise AcquisitionError(f"Nie udało się nadać unikalnego capture_id dla {prefix}.")


def do_capture(study_dir: Path, station: dict, profile: dict, profile_sha: str,
               tuning_sha: str, session: dict) -> int:
    sample = session.get("sample")
    if not sample:
        raise AcquisitionError(
            "Nie zadeklarowano próbki. Tożsamość i werdykt eksperta deklaruje się\n"
            "  przed ujęciem, nie po (§0).")
    check_disk(station)

    frame = sample["frame_seq"] + 1  # inkrement dopiero po akceptacji (§5)
    capture_id = allocate_capture_id(study_dir, session, sample, frame)

    staging = study_dir / ".tmp" / capture_id
    staging.mkdir(parents=True)
    image = staging / f"capture.{profile['encoding']}"
    meta_path = staging / "meta.json"

    command = build_command(station, profile, image, meta_path)
    print(f"Ujęcie {capture_id} …")
    run_capture(command)

    if not image.exists():
        raise AcquisitionError(f"rpicam-still nie zapisał obrazu: {image}")
    try:
        raw_meta = read_json(meta_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise AcquisitionError(
            f"Nie da się odczytać metadanych ujęcia ({exc}). Zdjęcie z niezweryfikowanymi\n"
            "  parametrami jest gorsze niż brak zdjęcia (§0).")

    checks, warnings = verify_contract(raw_meta, profile, session)
    violations = [c for c in checks if c["status"] in ("naruszenie", "brak")]
    accepted = not violations

    write_json(meta_path, enrich_meta(raw_meta, profile, profile_sha, tuning_sha,
                                      session, command))
    acquisition = {
        "capture_id": capture_id,
        "study_id": session["study_id"],
        "batch_id": sample["batch_id"],
        "sample_id": sample["sample_id"],
        "layout_seq": sample["layout_seq"],
        "frame_seq": frame,
        "session_id": session["session_id"],
        "profile_id": profile["profile_id"],
        "profile_sha256": profile_sha,
        "timestamp": now_iso(),
        "operator": session["operator"],
        "conditions": {
            "illuminator_id": session["illuminator_id"],
            "illuminator_on_since": session["illuminator_on_since"],
            "temperature_c": session["temperature_c"],
            "session_notes": session["notes"],
        },
        "sample": {k: v for k, v in sample.items()
                   if k not in ("layout_seq", "frame_seq")},
        "no_calibration": session["no_calibration"],
        "calibration": profile["calibration"],
        "qc": {"status": "not_run", "reason": "QC §6 nieobjęte tym programem"},
        "contract": {
            "status": "ok" if accepted else "rejected",
            "checks": checks,
            "warnings": warnings,
        },
        "command_line": command,
        "tools": session["tools"],
    }
    write_json(staging / "acquisition.json", acquisition)

    sums = write_checksums(staging)
    verify_checksums(staging, sums)

    destination = study_dir / ("captures" if accepted else "rejected") / capture_id
    try:
        os.rename(staging, destination)
    except OSError as exc:
        raise AcquisitionError(
            f"Nie udało się domknąć zapisu {capture_id} ({exc}).\n"
            "  Pliki zostają w .tmp/ i przy następnym uruchomieniu trafią do rejected/\n"
            "  z przyczyną 'zapis niedokończony'. Archiwum nie zostało naruszone.")
    fsync_dir(destination.parent)

    if accepted:
        sample["frame_seq"] = frame
        session["counts"]["accepted"] += 1
        if session.get("reference_ccm") is None:
            session["reference_ccm"] = raw_meta.get("ColourCorrectionMatrix")
        if session.get("reference_lux") is None:
            session["reference_lux"] = raw_meta.get("Lux")
    else:
        session["counts"]["rejected"] += 1
    session["last_lux"] = raw_meta.get("Lux")
    write_json(session_path(study_dir), session)

    append_manifest(study_dir, {
        "capture_id": capture_id,
        "study_id": session["study_id"],
        "batch_id": sample["batch_id"],
        "sample_id": sample["sample_id"],
        "layout_seq": sample["layout_seq"],
        "frame_seq": frame,
        "session_id": session["session_id"],
        "profile_id": profile["profile_id"],
        "timestamp": acquisition["timestamp"],
        "expert_verdict": sample["expert_verdict"],
        "protocol_stage": sample["protocol_stage"],
        "contract_status": acquisition["contract"]["status"],
        "qc_status": "not_run",
        "image_sha256": sums.get(image.name),
    })
    journal(study_dir, "capture_accepted" if accepted else "capture_rejected", {
        "capture_id": capture_id, "session_id": session["session_id"],
        "path": str(destination),
        "violations": [f"{c['field']}: {c['status']}" for c in violations],
    })

    report_capture(destination, acquisition, checks, warnings, accepted, sample)
    if accepted and sample["protocol_stage"] == "B":
        print("  Etap B — przesyp materiał przed kolejnym ujęciem (--layout).")
    return EXIT_OK if accepted else EXIT_REJECTED


def report_capture(destination: Path, acquisition: dict, checks: list, warnings: list,
                   accepted: bool, sample: dict) -> None:
    mark = "✓" if accepted else "✗"
    print(f"\n{mark} L{sample['layout_seq']:02d}F{acquisition['frame_seq']:02d}  "
          f"{acquisition['capture_id']}")
    print(f"  {destination}")
    for check in checks:
        if check["status"] == "ok":
            continue
        if check["status"] == "odniesienie":
            print(f"  · {check['field']}: odniesienie sesji ustalone")
        else:
            print(f"  ! {check['field']}: zmierzone {check['actual']}, "
                  f"profil {check['expected']}"
                  + (f" ±{check['tolerance']}" if "tolerance" in check else ""))
    for warning in warnings:
        print(f"  ~ {warning}")
    if accepted:
        print("  kontrakt akwizycji: ok")
    else:
        print("  ODRZUCONE — frame_seq bez zmian, powtórz ujęcie.")
        print("  Pliki zachowane w rejected/ jako dowód rozjechania stanowiska (§5).")


# --------------------------------------------------------------------------- #
# Zamknięcie sesji
# --------------------------------------------------------------------------- #

def end_session(study_dir: Path, session: dict) -> None:
    events = []
    journal_file = study_dir / "journal.jsonl"
    if journal_file.exists():
        with journal_file.open("r", encoding="utf-8") as f:
            events = [json.loads(line) for line in f if line.strip()]
    mine = [e for e in events if e.get("session_id") == session["session_id"]]

    rejected = [e for e in mine if e["event"] == "capture_rejected"]
    reasons: dict[str, int] = {}
    for event in rejected:
        for violation in event.get("violations", []):
            reasons[violation] = reasons.get(violation, 0) + 1
    unassessed = [e for e in mine if e["event"] == "sample_declared"
                  and e.get("expert_verdict") == "nieoceniony"]

    session["ended_at"] = now_iso()
    session["summary"] = {
        "accepted": session["counts"]["accepted"],
        "rejected": session["counts"]["rejected"],
        "rejection_reasons": reasons,
        "samples": len(session["samples_seen"]),
        "samples_unassessed": len(unassessed),
        "lux_first": session.get("reference_lux"),
        "lux_last": session.get("last_lux"),
    }
    write_json(study_dir / "sessions" / f"{session['session_id']}.json", session)
    session_path(study_dir).unlink()
    journal(study_dir, "session_end", {"session_id": session["session_id"],
                                       **session["summary"]})

    summary = session["summary"]
    print(f"\nSesja {session['session_id']} zamknięta.")
    print(f"  ujęcia zapisane:  {summary['accepted']}")
    print(f"  odrzucone:        {summary['rejected']}")
    for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"      {count}× {reason}")
    print(f"  próbki:           {summary['samples']}"
          + (f" (bez oceny eksperta: {summary['samples_unassessed']})"
             if summary["samples_unassessed"] else ""))
    if summary["lux_first"] and summary["lux_last"]:
        drift = (summary["lux_last"] - summary["lux_first"]) / summary["lux_first"] * 100
        print(f"  dryf oświetlenia: Lux {summary['lux_first']:.1f} → "
              f"{summary['lux_last']:.1f} ({drift:+.1f}%)")
    print("  QC §6 nie było liczone — wzorce i ostrość niesprawdzone.")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Akwizycja jednej próbki — jedno ujęcie na wywołanie (spec-akwizycji.md)",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-c", "--config", required=True, type=Path,
                        help="plik konfiguracji stanowiska (station.json)")

    action = parser.add_argument_group("tryb")
    action.add_argument("--layout", action="store_true",
                        help="przesypano materiał: layout_seq += 1, frame_seq = 1")
    action.add_argument("--session-end", action="store_true",
                        help="zamknięcie sesji i podsumowanie")

    sample = parser.add_argument_group("deklaracja próbki (§8)")
    sample.add_argument("--batch", help="identyfikator dostawy")
    sample.add_argument("--sample", help="identyfikator próbki")
    sample.add_argument("--supplier")
    sample.add_argument("--material", help="typ materiału / frakcja")
    sample.add_argument("--verdict", help="werdykt eksperta ze słownika study.json")
    sample.add_argument("--reasons", help="przyczyny po przecinku, słownik kontrolowany")
    sample.add_argument("--verdict-author")
    sample.add_argument("--verdict-date", help="RRRR-MM-DD, jeśli inna niż data zdjęcia")
    sample.add_argument("--stage", help="etap protokołu (§9)")
    sample.add_argument("--notes")

    session = parser.add_argument_group("sesja (§4)")
    session.add_argument("--operator", help="nadpisuje operatora z konfiguracji")
    session.add_argument("--temperature", type=float, help="temperatura otoczenia [°C]")
    session.add_argument("--illuminator-on-since",
                         help="godzina włączenia oświetlacza, np. 08:15")
    session.add_argument("--session-notes")
    session.add_argument("--no-calibration", action="store_true",
                         help="świadoma praca bez flat-fielda/skali; flaga trafia "
                              "do każdego rekordu sesji (§7)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        station = load_station(args.config)
        profile, profile_sha = load_profile(station["profile_path"])
        tuning_sha = verify_tuning_file(profile)

        station["archive_root"].mkdir(parents=True, exist_ok=True)
        study_dir = ensure_study(station, profile, profile_sha)
        for name in recover_interrupted(study_dir):
            print(f"UWAGA: niedokończony zapis {name} przeniesiony do rejected/.")

        session = load_session(study_dir)
        if session is None:
            if args.session_end:
                raise AcquisitionError("Nie ma otwartej sesji.")
            session = start_session(study_dir, station, profile, profile_sha,
                                    tuning_sha, args)
            print(f"Sesja {session['session_id']} · profil {profile['profile_id']} "
                  f"· operator {session['operator']}")
        else:
            verify_session_profile(session, profile, profile_sha, tuning_sha)

        if args.session_end:
            end_session(study_dir, session)
            return EXIT_OK

        check_calibration(study_dir, profile, session, args.no_calibration)

        if args.batch or args.sample:
            sample = declare_sample(study_dir, session, station["study"], args)
            print(f"Próbka {sample['batch_id']}/{sample['sample_id']} · "
                  f"werdykt {sample['expert_verdict']}"
                  + (f" · {', '.join(sample['verdict_reasons'])}"
                     if sample["verdict_reasons"] else "")
                  + f" · etap {sample['protocol_stage']}")
            return EXIT_OK

        if args.layout:
            sample = advance_layout(study_dir, session)
            print(f"Przesypano — ułożenie {sample['layout_seq']}, licznik ujęć od 1.")
            return EXIT_OK

        return do_capture(study_dir, station, profile, profile_sha, tuning_sha, session)

    except AcquisitionError as exc:
        sys.stdout.flush()
        print(f"\nBŁĄD: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except (OSError, json.JSONDecodeError) as exc:
        sys.stdout.flush()
        print(f"\nBŁĄD: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except KeyboardInterrupt:
        sys.stdout.flush()
        print("\nPrzerwano.", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
