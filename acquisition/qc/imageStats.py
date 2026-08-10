#!/usr/bin/env python3
"""Statystyki obrazu potrzebne kalibracji stanowiska — numpy + Pillow, bez OpenCV.

Moduł jest **tymczasowy z założenia**. Gdy warstwa 2 zostanie przeniesiona z
`analiza3/`, te funkcje muszą zostać zastąpione wspólnym `spec_common.py`:
QC w akwizycji i pomiar w analizie liczące te same wielkości dwoma niezależnymi
kodami rozjadą się prędzej czy później, a wtedy progi wyznaczone na jednym
przestaną obowiązywać na drugim (spec-akwizycji.md §12.13).

Konwersja sRGB→CIELAB przyjmuje sRGB z iluminantem D65 i punktem bieli D65.
To jest skala **przyrządowa**: opisuje wyjście ISP przy zamrożonym profilu,
a nie kolorymetrię sceny. Przeliczenie na skalę kolorymetryczną wymaga karty
barw w kadrze (spec-akwizycji.md §7, ujęcie `colorchart`).

Kadr 4056×3040 ma 12,3 Mpx, więc pełnoklatkowe operacje w float32 kosztują
~50 MB na kanał. Funkcje pracujące na całym kadrze liczą blokami wierszy.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

ROW_CHUNK = 256

# sRGB D65 — macierz i punkt bieli wg IEC 61966-2-1
_M_RGB_TO_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                          [0.2126729, 0.7151522, 0.0721750],
                          [0.0193339, 0.1191920, 0.9503041]], dtype=np.float32)
_WHITE_D65 = np.array([0.95047, 1.00000, 1.08883], dtype=np.float32)


def load_rgb(path) -> np.ndarray:
    """PNG → tablica uint8 (H, W, 3). Bez skalowania i bez konwersji profilu."""
    with Image.open(path) as image:
        if image.mode != "RGB":
            image = image.convert("RGB")
        return np.asarray(image, dtype=np.uint8)


def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """(..., 3) uint8/float w skali 0–255 → (..., 3) float32 L*a*b*."""
    values = np.asarray(rgb, dtype=np.float32) / 255.0
    linear = np.where(values <= 0.04045, values / 12.92,
                      ((values + 0.055) / 1.055) ** 2.4)
    xyz = linear @ _M_RGB_TO_XYZ.T / _WHITE_D65
    delta = 6.0 / 29.0
    f = np.where(xyz > delta ** 3, np.cbrt(xyz), xyz / (3 * delta * delta) + 4.0 / 29.0)
    return np.stack([116.0 * f[..., 1] - 16.0,
                     500.0 * (f[..., 0] - f[..., 1]),
                     200.0 * (f[..., 1] - f[..., 2])], axis=-1)


def lightness_full(rgb: np.ndarray) -> np.ndarray:
    """L* całego kadru, liczone blokami wierszy — (H, W) float32."""
    height = rgb.shape[0]
    out = np.empty(rgb.shape[:2], dtype=np.float32)
    for start in range(0, height, ROW_CHUNK):
        stop = min(start + ROW_CHUNK, height)
        out[start:stop] = srgb_to_lab(rgb[start:stop])[..., 0]
    return out


def luma(rgb: np.ndarray) -> np.ndarray:
    """Luminancja w DN (bez linearyzacji) — do progowania i oceny ostrości."""
    weights = np.array([0.299, 0.587, 0.114], dtype=np.float32)
    return (rgb.astype(np.float32) @ weights)


# --------------------------------------------------------------------------- #
# Miary kadru
# --------------------------------------------------------------------------- #

def frame_stats(rgb: np.ndarray, clip_dn: int = 250,
                bright_percentile: float = 99.9) -> dict:
    """max_dn, clip_frac, mean_dn i poziom najjaśniejszych pikseli (§6, §4 rekomendacji).

    `bright_dn` to percentyl, a nie maksimum: pojedynczy gorący piksel albo odbłysk
    na ziarnie nie może decydować o czasie naświetlania całej serii.
    """
    counts = np.zeros(256, dtype=np.int64)
    for channel in range(3):
        counts += np.bincount(rgb[..., channel].ravel(), minlength=256)
    total = counts.sum()
    cumulative = np.cumsum(counts)
    return {
        "max_dn": int(np.nonzero(counts)[0][-1]),
        "clip_frac": float(counts[clip_dn:].sum() / total),
        "clip_dn": clip_dn,
        "mean_dn": float((counts * np.arange(256)).sum() / total),
        "bright_dn": int(np.searchsorted(cumulative, total * bright_percentile / 100.0)),
        "bright_percentile": bright_percentile,
    }


def otsu_threshold(gray: np.ndarray) -> float:
    counts = np.bincount(np.clip(gray, 0, 255).astype(np.uint8).ravel(), minlength=256)
    levels = np.arange(256, dtype=np.float64)
    total = counts.sum()
    weight_bg = np.cumsum(counts)
    weight_fg = total - weight_bg
    sum_bg = np.cumsum(counts * levels)
    sum_all = sum_bg[-1]
    valid = (weight_bg > 0) & (weight_fg > 0)
    variance = np.zeros(256, dtype=np.float64)
    variance[valid] = (weight_bg[valid] * weight_fg[valid]
                       * ((sum_bg[valid] / weight_bg[valid])
                          - ((sum_all - sum_bg[valid]) / weight_fg[valid])) ** 2)
    return float(np.argmax(variance))


def laplacian_variance(gray: np.ndarray) -> float:
    """Wariancja laplasjanu — miara ostrości (§6). Liczyć na stałym ROI, nie na kadrze."""
    values = gray.astype(np.float32)
    lap = (values[:-2, 1:-1] + values[2:, 1:-1] + values[1:-1, :-2] + values[1:-1, 2:]
           - 4.0 * values[1:-1, 1:-1])
    return float(lap.var())


# --------------------------------------------------------------------------- #
# ROI
# --------------------------------------------------------------------------- #

def crop(rgb: np.ndarray, roi, erosion: int = 0) -> np.ndarray:
    """ROI [x, y, w, h] z opcjonalną erozją brzegu.

    Erozja jest konieczna przy wzorcach: halo wyostrzania sięga ~10 px, a filtr CDN
    miesza chromę na kilku px, więc brzeg płytki nie opisuje jej materiału.
    """
    x, y, w, h = roi
    x0, y0 = x + erosion, y + erosion
    x1, y1 = x + w - erosion, y + h - erosion
    if x0 >= x1 or y0 >= y1:
        raise ValueError(f"ROI {roi} po erozji {erosion} px jest puste")
    return rgb[y0:y1, x0:x1]


def patch_stats(rgb: np.ndarray, roi, erosion: int = 30) -> dict:
    """Statystyki wzorca fotometrycznego: mediany L*a*b*, rozrzut, przesterowanie."""
    region = crop(rgb, roi, erosion)
    lab = srgb_to_lab(region)
    lightness = lab[..., 0]
    return {
        "roi": list(roi),
        "erosion_px": erosion,
        "n_px": int(region.shape[0] * region.shape[1]),
        "rgb_median": [float(np.median(region[..., c])) for c in range(3)],
        "L_median": float(np.median(lightness)),
        "a_median": float(np.median(lab[..., 1])),
        "b_median": float(np.median(lab[..., 2])),
        "L_sd": float(lightness.std()),
        "L_p05": float(np.percentile(lightness, 5)),
        "L_p95": float(np.percentile(lightness, 95)),
        "max_dn": int(region.max()),
        "p99_dn": int(np.percentile(region, 99)),
        "clip_frac": float((region >= 250).mean()),
    }


def illumination_range(lightness: np.ndarray, tiles=(8, 6),
                       percentile: float = 98.0) -> dict:
    """Rozpiętość P98 L* po siatce kafli — wskaźnik równomierności pola (§6, §12.7).

    Tą liczbą mierzy się skuteczność korekcji flat-field po utracie bloku ALSC
    w pliku strojenia scientific.
    """
    height, width = lightness.shape
    columns, rows = tiles
    grid = np.zeros((rows, columns), dtype=np.float32)
    for row in range(rows):
        for column in range(columns):
            tile = lightness[row * height // rows:(row + 1) * height // rows,
                             column * width // columns:(column + 1) * width // columns]
            grid[row, column] = np.percentile(tile, percentile)
    return {
        "tiles": [columns, rows],
        "percentile": percentile,
        "grid_L": grid.round(3).tolist(),
        "min_L": float(grid.min()),
        "max_L": float(grid.max()),
        "range_L": float(grid.max() - grid.min()),
    }
