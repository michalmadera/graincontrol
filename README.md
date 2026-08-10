# GrainControl

Platforma kontroli jakości materiału sypkiego na podstawie obrazu: od akwizycji zdjęcia
na zamrożonych parametrach, przez pomiar barwy i kształtu pojedynczych ziaren, po werdykt
akceptacji dostawy wydawany na stanowisku magazynowym.

Pierwsze zastosowanie: ocena wtrąceń w kruszywie przy przyjęciu dostawy u producenta
chemii budowlanej.

## Warstwy

Repozytorium obejmuje dwa tory, rozdzielone jednokierunkową zależnością: tor badawczy
produkuje **profil oceny**, tor operacyjny go konsumuje i nigdy nie modyfikuje.

| # | warstwa | katalog | produkt |
|---|---|---|---|
| 1 | Akwizycja | [acquisition/](acquisition/) | zdjęcie PNG + metadane, na zweryfikowanym kontrakcie akwizycji |
| 2 | Pomiar | [measurement/](measurement/) | maski ziaren → metryki barwy i kształtu na ziarno i na próbkę |
| 3 | Kalibracja progów | [calibration/](calibration/) | plik profilu oceny (JSON + SHA-256) |
| 4 | Decyzja | [station/](station/), [service/](service/), [panel/](panel/) | werdykt pomiaru i status dostawy w ruchu produkcyjnym |

Warstwy 1–3 to tor badawczy, warstwa 4 to system operacyjny. Podział opisany
w [docs/spec-analizy-barwy.md](docs/spec-analizy-barwy.md) §1
i [docs/spec-operacyjny.md](docs/spec-operacyjny.md) §1.5.

## Struktura

```
graincontrol/
├── docs/            specyfikacje funkcjonalne i wytyczne
├── acquisition/     warstwa 1 — kontrakt akwizycji, sterowanie kamerą
├── measurement/     warstwa 2 — segmentacja, metryki barwy i kształtu
├── calibration/     warstwa 3 — rozkłady z wielu próbek → profil oceny
├── station/         aplikacja stacji pomiarowej (RPi, tryb kiosk)
├── service/         serwis analizujący (REST API + GPU)
├── panel/           panel laboratorium (aplikacja przeglądarkowa)
├── profiles/        wersjonowane profile akwizycji i profile oceny
└── libs/            wspólne schematy JSON, klient API, typy
```

`calibration/` zapisuje do `profiles/`, `service/` tylko stamtąd czyta — granica między
torami jest widoczna w drzewie katalogów.

## Dokumenty

| dokument | rola |
|---|---|
| [docs/spec-przygotowanie-materialu.md](docs/spec-przygotowanie-materialu.md) | instrukcja stanowiskowa: przygotowanie i rozsypanie próbki |
| [docs/spec-akwizycji.md](docs/spec-akwizycji.md) | warstwa 1 — zamrożenie i weryfikacja parametrów zdjęcia |
| [docs/spec-analizy-barwy.md](docs/spec-analizy-barwy.md) | warstwa 2 — metryki barwy na ziarno i na próbkę |
| [docs/spec-analizy-ksztaltu.md](docs/spec-analizy-ksztaltu.md) | warstwa 2 — metryki kształtu |
| [docs/spec-operacyjny.md](docs/spec-operacyjny.md) | warstwa 4 — system operacyjny: stacja, serwis, panel |
| [docs/wytyczne-barwy.md](docs/wytyczne-barwy.md), [docs/wytyczne-ksztalty.md](docs/wytyczne-ksztalty.md) | wytyczne wejściowe do specyfikacji pomiarowych |
| [docs/rekomendacja.md](docs/rekomendacja.md) | stan strojenia toru optycznego i lista rzeczy do zrobienia |

## Zasady

- **Profil oceny jest jedynym źródłem progów.** Nie ma progów w kodzie ani w formularzu
  panelu — jest plik JSON o znanej sumie kontrolnej ([docs/spec-operacyjny.md](docs/spec-operacyjny.md) §6.1).
- **Profil obowiązuje tylko w warunkach, w których powstał.** Warunki ważności
  (profil akwizycji, model masek, wersja pipeline'u, format zdjęcia) są sprawdzane przy
  wczytaniu; niezgodność jest błędem, nie ostrzeżeniem (BR-014).
- **Zapis wyłącznie bezstratny (PNG).** Kompresja stratna przesuwa składowe a\* i b\* —
  czyli dokładnie te wielkości, na których oparte są progi.
- **Werdykt musi być odtwarzalny.** Przy każdym pomiarze zapisywane są: identyfikator
  i suma kontrolna profilu, wersja modelu masek i wersja pipeline'u (NFR-011).

## Status

Warstwa 2 jest zaimplementowana prototypowo poza tym repozytorium (`rpi_cam/analiza3/`).
Warstwy 1, 3 i 4 są na etapie specyfikacji. Kod nie został jeszcze przeniesiony —
katalogi warstw zawierają na razie wyłącznie opis zakresu.
