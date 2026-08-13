#!/usr/bin/env python3
"""Raport z sesji akwizycji — integralność, kontrakt, wzorce, rozdzielczość klas.

Odpowiada na pytanie, którego nie da się zadać pojedynczemu zdjęciu: *czy ta sesja
nadaje się do analizy, a jeśli nie, to co ją psuje*. Liczy trzy rzeczy, które psują
sesję po cichu:

  * **dryf w obrębie sesji** — L* wzorca bieli w czasie. Jeśli dryf jest porównywalny
    z różnicą między klasami materiału, wynik opisuje oświetlacz, nie materiał.
  * **niespójność ewidencji** — pliki bez wpisu, wpisy bez plików, powtórzone
    identyfikatory. Manifest jest indeksem, katalogi są prawdą (§10.1), więc
    rozjazd rozstrzygamy na korzyść katalogów.
  * **rozdzielczość klas** — czy etykiety w ogóle różnią się mierzalnie, i o ile
    w stosunku do rozrzutu wewnątrz etykiety.

    sessionReport.py data/sesja_20260813_1205
    sessionReport.py <sesja> --no-images        # sama ewidencja, bez czytania PNG
    sessionReport.py <sesja> --rebuild-manifest # odtwórz manifest ze skanu katalogów
    sessionReport.py <sesja> --json raport.json

Zależności: numpy + Pillow (tylko przy analizie obrazu).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

_ACQUISITION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ACQUISITION / "qc"))

MANIFEST_COLUMNS = ["capture_id", "session", "label", "index", "timestamp",
                    "profile_id", "contract_status", "dummy", "image_sha256"]
PATCH_EXCLUDE_MARGIN = 80
PATCH_L_WARN = 0.5      # §6: |Δ| L* wzorca bieli wobec expected
PATCH_SD_WARN = 1.5     # §6: sd L* w ROI bieli


# --------------------------------------------------------------------------- #
# Skan katalogu sesji
# --------------------------------------------------------------------------- #

def scan_captures(session: Path) -> tuple[list[dict], list[dict]]:
    """Ujęcia przyjęte i odrzucone, odczytane z rekordów na dysku."""
    accepted, rejected = [], []
    for record_path in sorted(session.rglob("*_acquisition.json")):
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  ! nieczytelny rekord {record_path.name}: {exc}")
            continue
        record["_dir"] = record_path.parent
        record["_stem"] = record_path.name[: -len("_acquisition.json")]
        (rejected if "odrzucone" in record_path.parts else accepted).append(record)
    return accepted, rejected


def check_integrity(session: Path, captures: list[dict]) -> dict:
    """Komplet plików, zgodność sum, wpisy-widma i powtórzone identyfikatory."""
    issues = {"brak_plikow": [], "sumy": [], "sierotki": [],
              "manifest_bez_plikow": [], "duplikaty": []}

    on_disk = {}
    for record in captures:
        stem, folder = record["_stem"], record["_dir"]
        for suffix in (".png", ".dng", "_meta.json", ".sha256"):
            if not (folder / f"{stem}{suffix}").exists():
                issues["brak_plikow"].append(f"{stem}{suffix}")
        sha_file = folder / f"{stem}.sha256"
        if sha_file.exists():
            for line in sha_file.read_text(encoding="utf-8").splitlines():
                digest, _, name = line.partition("  ")
                target = folder / name
                if not target.exists():
                    issues["brak_plikow"].append(name)
                elif hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    issues["sumy"].append(name)
        png = folder / f"{stem}.png"
        if png.exists():
            # klucz jak w manifeście: odrzucone mają capture_id ze znacznikiem czasu,
            # bo numer rośnie dopiero po przyjęciu i sam stem nie jest unikalny
            on_disk[record.get("capture_id", stem)] = hashlib.sha256(
                png.read_bytes()).hexdigest()

    # PNG bez markera .sha256 = zapis przerwany albo ręczna ingerencja
    for png in session.rglob("*.png"):
        if png.parent.name.startswith("."):
            continue
        if not png.with_suffix(".sha256").exists():
            issues["sierotki"].append(str(png.relative_to(session)))

    manifest = read_manifest(session)
    seen = defaultdict(list)
    for row in manifest:
        seen[row["capture_id"]].append(row)
    for capture_id, rows in seen.items():
        if len(rows) > 1:
            issues["duplikaty"].append(
                f"{capture_id}: {len(rows)}× ({', '.join(r['timestamp'][11:19] for r in rows)})")
        if capture_id not in on_disk:
            issues["manifest_bez_plikow"].append(capture_id)
    return {"issues": issues, "manifest": manifest, "on_disk": on_disk}


def read_manifest(session: Path) -> list[dict]:
    path = session / "manifest.csv"
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def rebuild_manifest(session: Path, accepted: list[dict], rejected: list[dict]) -> int:
    """Odtworzenie indeksu ze skanu katalogów (§10.1, §12.5).

    Dziennika **nie** przepisujemy — jest dopisywany i nigdy edytowany. Sam fakt
    przebudowy trafia do niego jako zdarzenie, więc historia zostaje odtwarzalna.
    """
    rows = []
    for record in sorted(accepted + rejected, key=lambda r: r.get("timestamp", "")):
        png = record["_dir"] / f"{record['_stem']}.png"
        rows.append({
            "capture_id": record.get("capture_id", record["_stem"]),
            "session": record.get("session", session.name),
            "label": record.get("label", ""),
            "index": record.get("index", ""),
            "timestamp": record.get("timestamp", ""),
            "profile_id": record.get("profile_id", ""),
            "contract_status": record.get("contract", {}).get("status", ""),
            "dummy": record.get("dummy", ""),
            "image_sha256": (hashlib.sha256(png.read_bytes()).hexdigest()
                             if png.exists() else ""),
        })
    with (session / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    with (session / "journal.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
            "event": "manifest_rebuilt", "rows": len(rows),
            "reason": "odtworzenie indeksu ze skanu katalogów (sessionReport)",
        }, ensure_ascii=False) + "\n")
    return len(rows)


# --------------------------------------------------------------------------- #
# Metadane i kontrakt
# --------------------------------------------------------------------------- #

def parameter_stability(captures: list[dict]) -> dict:
    """Ile różnych wartości przyjął każdy parametr w sesji — §14 „wymuszanie parametrów"."""
    keys = ("ExposureTime", "AnalogueGain", "DigitalGain", "ColourGains",
            "ColourCorrectionMatrix", "Lux", "ColourTemperature")
    values = {k: set() for k in keys}
    for record in captures:
        meta_path = record["_dir"] / f"{record['_stem']}_meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for key in keys:
            if meta.get(key) is not None:
                values[key].add(json.dumps(meta[key]))
    return {k: sorted(v) for k, v in values.items()}


def find_profile(captures: list[dict], explicit: Path | None) -> tuple[dict | None, str]:
    if explicit:
        return json.loads(explicit.read_text(encoding="utf-8")), str(explicit)
    ids = {r.get("profile_id") for r in captures if r.get("profile_id")}
    if len(ids) != 1:
        return None, f"w sesji {len(ids)} różnych profili: {sorted(ids)}"
    path = _ACQUISITION.parent / "profiles" / "acquisition" / f"{ids.pop()}.json"
    if not path.exists():
        return None, f"nie znaleziono pliku profilu {path.name}"
    profile = json.loads(path.read_text(encoding="utf-8"))
    recorded = {r.get("profile_sha256") for r in captures if r.get("profile_sha256")}
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    note = str(path)
    if recorded and actual not in recorded:
        note += "  ⚠ plik profilu w repozytorium RÓŻNI SIĘ od tego, którym zbierano"
    return profile, note


# --------------------------------------------------------------------------- #
# Analiza obrazu
# --------------------------------------------------------------------------- #

def analyse_images(captures: list[dict], profile: dict) -> list[dict]:
    import numpy as np
    import imageStats as st

    patches = {p["name"]: p["roi"] for p in (profile.get("reference_patches") or [])}
    exclude = None
    if patches:
        xs = [r[0] for r in patches.values()] + [r[0] + r[2] for r in patches.values()]
        ys = [r[1] for r in patches.values()] + [r[1] + r[3] for r in patches.values()]
        exclude = (min(xs) - PATCH_EXCLUDE_MARGIN, min(ys) - PATCH_EXCLUDE_MARGIN,
                   max(xs) + PATCH_EXCLUDE_MARGIN, max(ys) + PATCH_EXCLUDE_MARGIN)

    out = []
    for n, record in enumerate(captures, 1):
        png = record["_dir"] / f"{record['_stem']}.png"
        if not png.exists():
            continue
        if sys.stdout.isatty():   # przy przekierowaniu pasek postępu tylko śmieci
            print(f"\r  czytam {n}/{len(captures)}: {record['_stem']:24s}",
                  end="", flush=True)
        rgb = st.load_rgb(png)
        gray = st.luma(rgb)
        mask = np.ones_like(gray, dtype=bool)
        if exclude:
            x0, y0, x1, y1 = exclude
            mask[max(0, y0):y1, max(0, x0):x1] = False   # wzorce poza pierwszym planem
        foreground = mask & (gray > st.otsu_threshold(gray))
        lab = st.srgb_to_lab(rgb[foreground])
        frame = st.frame_stats(rgb)
        entry = {
            "capture_id": record.get("capture_id", record["_stem"]),
            "label": record.get("label", ""),
            "timestamp": record.get("timestamp", ""),
            "max_dn": frame["max_dn"], "clip_frac": frame["clip_frac"],
            "mean_dn": frame["mean_dn"],
            "foreground_frac": float(foreground.mean()),
            "L": float(np.median(lab[:, 0])), "a": float(np.median(lab[:, 1])),
            "b": float(np.median(lab[:, 2])),
            "L_p10": float(np.percentile(lab[:, 0], 10)),
            "L_p90": float(np.percentile(lab[:, 0], 90)),
            "patches": {},
        }
        for name, roi in patches.items():
            stats = st.patch_stats(rgb, roi)
            entry["patches"][name] = {"L": stats["L_median"], "sd": stats["L_sd"],
                                      "a": stats["a_median"], "b": stats["b_median"],
                                      "max_dn": stats["max_dn"]}
        out.append(entry)
    if sys.stdout.isatty():
        print("\r" + " " * 60 + "\r", end="")
    return out


# --------------------------------------------------------------------------- #
# Raport
# --------------------------------------------------------------------------- #

def report(session: Path, args) -> dict:
    print(f"SESJA {session.name}")
    accepted, rejected = scan_captures(session)
    print(f"  ujęć przyjętych: {len(accepted)}   odrzuconych: {len(rejected)}")
    if not accepted and not rejected:
        print("  (brak rekordów akwizycji — czy to na pewno katalog sesji?)")
        return {}

    labels = defaultdict(int)
    for record in accepted:
        labels[record.get("label", "?")] += 1
    print("  etykiety: " + ", ".join(f"{k} ×{v}" for k, v in sorted(labels.items())))
    stamps = sorted(r.get("timestamp", "") for r in accepted if r.get("timestamp"))
    if len(stamps) > 1:
        span = datetime.fromisoformat(stamps[-1]) - datetime.fromisoformat(stamps[0])
        print(f"  czas trwania: {stamps[0][11:19]} → {stamps[-1][11:19]} ({span})")

    profile, profile_note = find_profile(accepted, args.profile)
    print(f"  profil: {profile_note}")

    # --- integralność
    print("\nINTEGRALNOŚĆ")
    integrity = check_integrity(session, accepted + rejected)
    issues = integrity["issues"]
    names = {"brak_plikow": "brakujące pliki",
             "sumy": "sumy kontrolne niezgodne",
             "sierotki": "PNG bez markera .sha256 (zapis przerwany?)",
             "manifest_bez_plikow": "wpisy w manifeście bez plików na dysku",
             "duplikaty": "powtórzone capture_id w manifeście"}
    clean = True
    for key, label in names.items():
        if issues[key]:
            clean = False
            print(f"  ✗ {label}: {len(issues[key])}")
            for item in issues[key][:10]:
                print(f"      {item}")
    if clean:
        print(f"  ✓ komplet plików, sumy zgodne, manifest zgodny z katalogami "
              f"({len(integrity['manifest'])} wierszy)")

    # --- kontrakt
    print("\nKONTRAKT AKWIZYCJI (§5)")
    statuses = defaultdict(int)
    for record in accepted + rejected:
        statuses[record.get("contract", {}).get("status", "?")] += 1
    print("  " + ", ".join(f"{k}: {v}" for k, v in sorted(statuses.items())))
    for record in rejected:
        bad = [c for c in record.get("contract", {}).get("checks", [])
               if c["status"] in ("naruszenie", "brak")]
        print(f"  ✗ {record.get('capture_id', record['_stem'])}: " + "; ".join(
            f"{c['field']} zmierzone {c['actual']}, profil {c['expected']}" for c in bad))

    stability = parameter_stability(accepted)
    for key, values in stability.items():
        if not values:
            continue
        mark = "✓" if len(values) == 1 else "✗"
        shown = values[0] if len(values) == 1 else f"{len(values)} różnych wartości"
        print(f"  {mark} {key:24s} {shown[:60]}")

    result = {"session": session.name, "accepted": len(accepted),
              "rejected": len(rejected), "labels": dict(labels),
              "issues": {k: v for k, v in issues.items() if v},
              "stability": {k: len(v) for k, v in stability.items() if v}}

    if args.no_images or profile is None:
        if profile is None:
            print("\n(analiza obrazu pominięta — nie ustalono profilu)")
        return result

    # --- obraz
    print("\nODCZYT OBRAZÓW")
    frames = analyse_images(accepted, profile)
    result["frames"] = frames
    if not frames:
        return result
    _report_patches(frames, profile)
    _report_frames(frames)
    _report_labels(frames, result)
    return result


def _report_patches(frames: list[dict], profile: dict) -> None:
    import numpy as np
    names = sorted({n for f in frames for n in f["patches"]})
    if not names:
        return
    print("\nWZORCE FOTOMETRYCZNE (§6)")
    expected = (profile.get("expected") or {}).get("white_patch_L")
    ordered = sorted(frames, key=lambda f: f["timestamp"])
    for name in names:
        series = np.array([f["patches"][name]["L"] for f in ordered])
        sds = np.array([f["patches"][name]["sd"] for f in ordered])
        drift = series[-1] - series[0]
        print(f"  {name:6s} L* {series.min():.2f}–{series.max():.2f} "
              f"(rozstęp {np.ptp(series):.2f})   dryf w sesji {drift:+.2f}   "
              f"sd {sds.min():.2f}–{sds.max():.2f}")
        if name == "white" and expected:
            deltas = series - expected
            outside = [f["capture_id"] for f, d in zip(ordered, deltas)
                       if abs(d) > PATCH_L_WARN]
            print(f"         wobec expected {expected}: {deltas.min():+.2f}…{deltas.max():+.2f}"
                  + (f"   ⚠ poza ±{PATCH_L_WARN}: {', '.join(outside)}" if outside else ""))
        loud = [(f["capture_id"], round(f["patches"][name]["sd"], 2))
                for f in ordered if f["patches"][name]["sd"] > PATCH_SD_WARN]
        if len(loud) > len(ordered) / 2:
            # Podwyższone sd we wszystkich ujęciach to własność samej płytki
            # (np. faktura rastrowa), a nie zdarzenie w sesji — nie ma sensu
            # wypisywać listy klatek, bo problem jest stały.
            print(f"         ⚠ sd powyżej {PATCH_SD_WARN} w {len(loud)}/{len(ordered)} ujęć"
                  f" — to cecha powierzchni wzorca, nie zanieczyszczenie pojedynczych klatek")
        elif loud:
            print(f"         ⚠ sd powyżej {PATCH_SD_WARN} (wzorzec zabrudzony?): {loud}")


def _report_frames(frames: list[dict]) -> None:
    import numpy as np
    print("\nKADR")
    max_dn = np.array([f["max_dn"] for f in frames])
    clip = np.array([f["clip_frac"] for f in frames])
    fg = np.array([f["foreground_frac"] for f in frames])
    print(f"  max_dn {max_dn.min()}–{max_dn.max()}   "
          f"klip {clip.max()*100:.3f}% (najwyższy)   "
          f"udział pierwszego planu {fg.min()*100:.1f}–{fg.max()*100:.1f}%")
    if clip.max() > 0:
        print("  ⚠ przesterowanie: piksele w saturacji tracą informację o barwie")
    if fg.min() < 0.20 or fg.max() > 0.90:
        print("  ⚠ udział pierwszego planu poza 20–90% (§6)")


def _report_labels(frames: list[dict], result: dict) -> None:
    import numpy as np
    groups = defaultdict(list)
    for f in frames:
        groups[f["label"]].append(f)
    if len(groups) < 2:
        return
    print("\nMATERIAŁ WEDŁUG ETYKIET")
    print(f"  {'etykieta':14s} {'n':>2s} {'L*':>15s} {'a*':>14s} {'b*':>14s} {'udział':>8s}")
    stats = {}
    for label, group in sorted(groups.items()):
        arr = {k: np.array([g[k] for g in group]) for k in ("L", "a", "b", "foreground_frac")}
        sd = lambda v: v.std(ddof=1) if len(v) > 1 else 0.0
        stats[label] = (arr["L"].mean(), sd(arr["L"]), len(group))
        print(f"  {label:14s} {len(group):2d} {arr['L'].mean():8.2f} ± {sd(arr['L']):4.2f} "
              f"{arr['a'].mean():7.2f} ± {sd(arr['a']):4.2f} "
              f"{arr['b'].mean():7.2f} ± {sd(arr['b']):4.2f} "
              f"{arr['foreground_frac'].mean()*100:7.1f}%")

    print("\n  rozdzielczość klas (ΔL* wobec rozrzutu wewnątrz klas):")
    names = sorted(stats)
    separations = []
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            (mx, sx, _), (my, sy, _) = stats[x], stats[y]
            pooled = np.sqrt((sx ** 2 + sy ** 2) / 2) or float("nan")
            d = abs(mx - my) / pooled
            separations.append({"a": x, "b": y, "delta_L": mx - my, "d": d})
            verdict = ("nierozróżnialne" if d < 1 else
                       "słabe" if d < 2 else "wyraźne" if d < 3 else "silne")
            print(f"    {x:14s} vs {y:14s} ΔL* {mx-my:+6.2f}   d = {d:5.2f}   {verdict}")
    result["separations"] = separations

    print("\n  Uwaga: to jest mediana L* całego pierwszego planu, a nie metryka na ziarno.")
    print("  Domieszka wtrąceń rzędu kilku procent nie rusza mediany — do jej wykrycia")
    print("  potrzebna jest segmentacja i rozkłady na ziarno (spec-analizy-barwy §5).")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("session", type=Path, help="katalog sesji")
    parser.add_argument("--profile", type=Path, help="plik profilu (domyślnie z rekordów)")
    parser.add_argument("--no-images", action="store_true",
                        help="pomiń odczyt PNG — sama ewidencja")
    parser.add_argument("--rebuild-manifest", action="store_true",
                        help="odtwórz manifest.csv ze skanu katalogów (§10.1)")
    parser.add_argument("--json", type=Path, help="zapisz wynik do pliku JSON")
    args = parser.parse_args(argv)

    session = args.session
    if not session.is_dir():
        print(f"BŁĄD: nie ma katalogu {session}", file=sys.stderr)
        return 1

    if args.rebuild_manifest:
        accepted, rejected = scan_captures(session)
        before = len(read_manifest(session))
        after = rebuild_manifest(session, accepted, rejected)
        print(f"Manifest odtworzony ze skanu katalogów: {before} → {after} wierszy.")
        print("Dziennik nietknięty — dopisano zdarzenie 'manifest_rebuilt'.\n")

    result = report(session, args)
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"\nZapisano {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
