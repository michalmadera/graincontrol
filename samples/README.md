# samples — obrazy referencyjne do rozwoju algorytmów

Mały, **niezmienny** zbiór pełnowymiarowych zdjęć PNG, na których rozwijamy i porównujemy
segmentację oraz metryki barwy i kształtu. Każdy obraz ma tutaj udokumentowane pochodzenie,
sumę kontrolną i znane wyniki pomiaru — inaczej nie da się stwierdzić, czy zmiana w kodzie
poprawiła algorytm, czy tylko zmieniła dane wejściowe.

> **To nie jest materiał kalibracyjny.** Progi wyznacza się wyłącznie na zdjęciach ze
> zweryfikowanym kontraktem akwizycji ([../docs/spec-akwizycji.md](../docs/spec-akwizycji.md)).
> Obrazy z tego katalogu mają kontrakt niezweryfikowany i służą wyłącznie do rozwoju kodu.

## Zasady katalogu

- **Tylko PNG bezstratny, pełna rozdzielczość.** Skalowanie i kompresja stratna przesuwają
  a\* i b\* oraz zmieniają liczbę pikseli na ziarno — czyli dokładnie to, co mierzymy.
- **Pliki są niezmienne.** Poprawiona wersja obrazu to nowa nazwa, nie nadpisanie —
  historia gita nie może rosnąć o kolejne kopie 17 MB.
- **Każdy obraz ma wpis w tabeli niżej** z sumą SHA-256 i statusem kontraktu akwizycji.
- **Limit praktyczny: kilka plików.** Powyżej ~5 obrazów (~100 MB) katalog przechodzi na
  Git LFS; przy plain gicie każdy klon ciągnie całą historię binariów.

## Zawartość

| plik | rozmiar | wymiary | kontrakt akwizycji | przeznaczenie |
|---|---|---|---|---|
| `stones2.png` | 16,2 MB | 4056×3040 RGB | **niezweryfikowany** | segmentacja, metryki barwy i kształtu, kotwica fotometryczna |
| `stones2_refpatches.json` | 3,4 kB | — | — | pochodzenie i model renderowania wzorców w `stones2.png` |

### stones2.png

SHA-256 `a3827813cfb8b5063a90874d78d0667ea41f2370e84300dc592b48bf679a70e1`
(zgodna z `image_sha256` w metadanych pomiaru — plik jest bit w bit tym, na którym
policzono wyniki niżej).

**Obraz jest hybrydą, nie surowym zdjęciem.** Powstał z `stones1.png` przez dorenderowanie
dwóch syntetycznych wzorców fotometrycznych w prawym dolnym rogu — kotwicy z
[../docs/spec-analizy-barwy.md](../docs/spec-analizy-barwy.md) §6.1. Materiał kamienny
w kadrze jest sfotografowany, wzorce nie. Algorytm, który traktuje wzorce jak obiekty
sceny, dostanie na nich wyniki idealne i nieprzenośne na prawdziwe zdjęcie.

| wzorzec | ρ | bbox (x, y, w, h) | L\* zmierzone | a\* | b\* |
|---|---|---|---|---|---|
| grey | 0,50 | 3527, 2009, 418, 418 | 56,372 | −3,453 | −5,500 |
| white | 0,99 | 3527, 2511, 418, 418 | 69,818 | −3,984 | −6,594 |

Bok wzorca 418 px = 15 mm; uzasadnienie doboru geometrii jest w
`stones2_refpatches.json` → `geometry_rationale`.

**Znane wyniki pomiaru** — punkt odniesienia przy zmianach w [../measurement/](../measurement/):

| wielkość | wartość |
|---|---|
| model masek | `cellpose-3.1.1.2/cyto3` |
| parametry masek | `diameter 35.0`, `flow_threshold 0.4`, `cellprob_threshold −1.0`, `channels [0,0]`, `seed 0` |
| instancje surowe / końcowe | 8105 / **8104** (1 odrzucona jako stykająca się z wzorcem) |
| próg Otsu | 97,0 DN |
| udział pierwszego planu | 0,5790 |
| recall pierwszego planu (px) | 0,9744 |
| wersja pipeline'u | `measure/0.1.0`, `segment-cellpose/0.1.0` |
| środowisko | Python 3.10.12, numpy 1.26.4, OpenCV 4.11.0, torch 2.1.2+cu121, cellpose 3.1.1.2, CUDA, `cudnn_deterministic` |

**Czego ten obraz nie daje:**

- Kontrakt akwizycji ma status `unverified` — brak pliku metadanych zdjęcia, nieznane
  parametry ISP, brak pliku strojenia, brak DNG, brak korekcji flat-field.
- Skala **35,9 µm/px jest założeniem** (obiektyw 12 mm z odległości 290 mm), nie pomiarem
  wzorca — patrz [../docs/spec-przygotowanie-materialu.md](../docs/spec-przygotowanie-materialu.md) §0.
  Każda metryka w milimetrach policzona z tego obrazu dziedziczy ten błąd.
- Rozsypanie nie było wykonane wg zamrożonej procedury, więc obraz nie mówi nic
  o σ_layout.

## Czego tu nie ma

Masek, tabel wyników i overlayów (`labels.npy` 49 MB, `stones.parquet`, `overlay.png`) —
są odtwarzalne z obrazu przez pipeline o wersji podanej wyżej i dlatego nie należą do
repozytorium. Archiwum zdjęć produkcyjnych też tu nie trafia: żyje na serwerze zgodnie
z [../docs/spec-operacyjny.md](../docs/spec-operacyjny.md) §NFR-003/NFR-007.
