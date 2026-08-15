# Wyniki 2026-08-15: rozróżnialność klas po kolorze (anchor-free)

Notatka robocza z sesji. Pytanie: **czy na podstawie koloru kamieni da się odróżnić trzy
klasy materiału** — `ladna_43`, `srednia_30`, `brzydka_27`. Kontynuacja
[2026-08-14](2026-08-14-segmentacja-metryki-plan-odbioru.md); tam kotwica bieli, tu odejście
od kotwicy na rzecz metody wewnątrzobrazowej.

Dane: `sesja_20260813_1205/` (3 klasy × 5 zdjęć, DNG/RAW). Maski: `inferencja_pelna/`
(grainnet doftrenowany, ciemne kamienie odzyskane). Env conda `kamyki`.

---

## 1. Punkt wyjścia — kotwica bieli była zawodna

Próba pomiaru koloru **bezwzględnego** (kotwica: biel karty → L\*=56,01 + neutralne a\*/b\*)
dawała **niestabilny** odczyt wzorca między zdjęciami:

| zdjęcie | biel L\* (stałe ROI z profilu) |
|---|---|
| brzydka_1 | 69,3 |
| brzydka_3 | 66,2 |
| ladna_1 | 66,1 |
| pozostałe 12 | ~62,2 |

Weryfikacja na **surowym Bayerze** (ten sam ROI, przed demozaikiem): jasność karty
**stała** we wszystkich 15 ujęciach (10 048–10 688 DN, rozrzut międzyklasowy <1%; brzydka
nie jaśniejsza), balans bieli **zablokowany identycznie** (2,360 / 1,000 / 2,190). Wyskok
L\*=69 pochodzi więc z **przetwarzania/treści** (karta w najciemniejszym rogu łapie ciepłe
odbicie), nie z oświetlenia ani materiału. **Wniosek:** kotwica na karcie w feralnym rogu
wprowadza więcej szumu niż koryguje. Odrzucona.

## 2. Metoda właściwa — „inny kolor niż reszta" (anchor-free)

Definicja eksperta „brzydki = inny kolor niż reszta" jest **względna wewnątrz jednej
partii**, więc kartonik jest zbędny: każdy kamień porównywany do **środka własnego
zdjęcia** (mediana barw ziaren). Oświetlenie się skraca — pomiar odporny.

Per kamień: mediana L\*a\*b\* wnętrza (`er5`, erozja 5 px, bez przecięcia z Otsu).
Odstający = ΔE00 (CIEDE2000) od środka własnego zdjęcia > próg. Zgodne ze
[spec-analizy-barwy.md](../docs/spec-analizy-barwy.md) §8 (wzorzec = mediana tej samej
partii; rozrzut w jednorodnym materiale sięga ΔE00 ≈ 6) i §9 pkt 6 (kierunkowość).

## 3. Wynik — odstające od własnej partii

Metoda **stabilna** zdjęcie po zdjęciu (żadnego wyskoku jak w §1):

| klasa | odstające ΔE00>5 | **ciemne** (L↓) | jasne (L↑) | **kremowe** (b↑, żółte) |
|---|---|---|---|---|
| **ladna** | **10,2 %** | 7,2 % | 1,9 % | 1,1 % |
| brzydka | 12,8 % | 8,2 % | 3,1 % | **1,4 %** |
| srednia | 13,6 % | 8,5 % | 4,1 % | 0,9 % |

(kierunek = dominująca składowa odchylenia odstającego ziarna)

## 4. Interpretacja

1. **Dominujący sygnał — ciemne (7–8,5 %) — to szum, nie materiał.** Kolor pojedynczego
   kamienia jest zdominowany geometrią (spec-analizy-barwy §9 pkt 1, R²≈0,13–0,19):
   ciemne = cień/bryła 3D. Potwierdza to kierunek — na ciemnych **srednia (8,5 %) ≥ brzydka
   (8,2 %)**, więc sygnał nie wskazuje nawet na brzydka.
2. **Jedyny materiałowy trop na brzydka — kremowe/żółte** (1,4 % vs srednia 0,9 %),
   zgodne z klasą `kremowy` (§6.1) i lekko kremowym materiałem. Ale efekt malutki, a
   **ladna (1,1 %) leży pomiędzy** — nie układa się w brzydka > srednia > ladna.
3. Separacja brzydka↔srednia **mieści się w szumie** `σ_layout`. Wg spec-analizy-barwy
   §9 pkt 3 („próg mieszczący się w szumie jest odrzucany") — **to nie jest próg**.

## 5. ⚠ Wniosek

- **Ładna — rozróżnialna.** Najbardziej jednorodna barwa (najmniej odstających), wynik
  **spójny przez 3 niezależne metody** (kotwica bezwzględna, odstające anchor-free, ΔE00
  kierunkowe). Sygnał **jednostronny**: „bardzo równy kolor" ⇒ dobra przesłanka za ładną;
  brak równości nie przesądza nic.
- **Brzydka vs srednia — nierozróżnialne po kolorze** na tych danych.
- Ograniczenie mocy: **jedna kupka na klasę** (n=1) — nie da się wyznaczyć granicy
  decyzyjnej, tylko opisać rozkład.

## 6. Czego brakuje — etap E

Spec-analizy-barwy §8E mówi wprost: bez **≥10 próbek z etykietą eksperta i podaną
przyczyną odrzucenia** (za ciemny / kremowy / zażółcony…) progów **nie da się wyznaczyć —
można tylko opisać, co jest typowe**. To najczęściej pomijany element badania.

**Rekomendacja:** narzędzie do etykietowania **per-kamień** (ekspert klika złe kamienie na
zdjęciu + powód ze słownika `verdict_reasons`). Dopiero taki zbiór daje materiał do
progów i klasyfikatora wtrąceń — zamiast zgadywania „inny kolor = zły".

Kod roboczy: scratchpad sesji (`kolor_anchored.py`, metoda anchor-free/ΔE00 kierunkowa).
