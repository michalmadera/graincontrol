# Wyniki 2026-08-14: segmentacja, metryki, plan odbioru partii

Notatka robocza z sesji: destylacja modelu segmentacji, pomiar metryk kształtu/barwy,
analiza wtrąceń, kotwica kolorystyczna i plan statystycznego odbioru partii (big bag).

Dane: `sesja_20260813_1205/` (4 klasy: brzydka_27, ladna_43, srednia_30, inna; po 5 zdjęć,
_5 = walidacja, _1..4 = trening). Model/kod: env conda `kamyki`, `model/training_grainnet`.

---

## 1. Segmentacja — grainnet doftrenowany na maskach cellpose

- **Teacher:** cellpose (cpsam, d=35) na 12 zdjęciach treningowych → maski instancji.
- **Kafelkowanie:** 512×512, stride 384 → **1056 kafli** (12×88), format grainnet.
- **Trening:** fine-tune z warm-startu `best_baseline.pt`, 40 epok, batch 4 → `checkpoints_gc/best4.pt`
  (produkcyjny `best4.pt` nietknięty). Best val 0,515 @ ep.37.
- **Wynik vs cellpose (walidacja, po deblobbingu):** średni **F1@IoU0.5 = 0,965**,
  liczba ziaren w granicach ~1–2%.

| czas (RTX 4070, klatka 4056×3040) | grainnet | cellpose |
|---|---|---|
| segmentacja | **~8,6 s** | ~26 s |
| pomiar metryk | ~15 s | ~15 s |
| pełny pipeline | **~24 s** | ~41 s |

**Wniosek:** grainnet ≈ cellpose przy ~3× szybszej inferencji. **Mieści się w budżecie
produkcyjnym ≤30 s** (spec-operacyjny §1.1), cellpose+pomiar (~41 s) — nie.

## 2. Czyszczenie masek — bloby i „nie-ziarna"

Dwa filtry (kolejność ważna):
1. **deblob:** `area > 10 × mediana pola ziarna` → usuwa gigantyczne blobs (tło 6–8 mln px).
2. **filtr „nie-ziarno":** `circularity < 0,4` LUB `solidity < 0,6` → usuwa **przerwy/sklejki**
   (segmentator etykietuje ciemne przerwy między ziarnami jako „ziarno"; mają circ ~0,17,
   solidity ~0,59 → geometrycznie to tło, nie kamień). Nie rusza realnych ziaren (P5 circ ~0,53).

Deblob NIE łapie tych średnich artefaktów (są ~3× mediana, poniżej progu 10×) — dlatego
potrzebny filtr po **kształcie**, nie po rozmiarze. Czyste maski: `grainnet_clean/`.

## 3. Metryki (kształt px + barwa)

Kod: `measure.py` (skimage.regionprops + rgb2lab + er5 przez transformatę odległości).
Rekordy per kamień: `sesja_20260813_1205/metryki/*_stones.csv`.

- **Kształt:** area, obwód (3 estymatory), kolistość (obie konwencje), solidity, AR (elipsa/Feret/
  minrect), roundness, elongation, extent, itd. Progi startowe C≥0,70 / AR≤1,50 / S≥0,90 →
  **~41% „OK"** we wszystkich klasach (progi nieskalibrowane, materiał kanciasty).
- **Barwa er5:** L/a/b median, C_ab, h_ab.

## 4. Kotwica kolorystyczna — auto-wykryta i użyta

- Wzorzec (szaro-biała karta, prawy górny róg) **wykryty analitycznie** (niska lokalna
  wariancja + jasność + prostokątność): karta ~287×311 px, dwie strefy szarości.
- **Cast toru** zmierzony na neutralnej szarości, spójny między próbkami:
  **off_a ≈ −5,3, off_b ≈ −7,4**.
- Po korekcie: **b_corr ≈ +3,6** → materiał realnie lekko **kremowy** (surowo wychodził
  ujemny przez niebieski cast toru). Kolor jest teraz **bezwzględny**.

## 5. ⚠ Kluczowy wynik: klasy się NIE rozdzielają

brzydka/ladna/srednia są **statystycznie takie same** na wszystkim, co zmierzono —
w medianie **i w ogonie**:

| próbka | %OK kształt | b_corr med | b_corr P95 | %żółte(>6) | %ciemne(L<40) |
|---|---|---|---|---|---|
| brzydka_27 | ~41% | 3,58 | 6,5 | 6,5% | 0,1% |
| ladna_43 | ~41% | 3,53 | 6,4 | 6,9% | 0,0% |
| srednia_30 | ~42% | 3,69 | 6,5 | 7,1% | 0,2% |
| inna | ~42% | 3,70 | 6,6 | 7,9% | 0,3% |

**brzydka nie ma więcej żółtych ani ciemnych niż ladna.** Barwa i kształt ziaren **nie kodują**
etykiet brzydka/ladna. Otwarte pytanie: **co konkretnie** znaczą te etykiety (zabrudzenie?
obce ziarna? drobna frakcja między ziarnami? wrażenie ogólne?) — bo w samych ziarnach różnicy
nie ma. **To trzeba ustalić z człowiekiem, który nazwał próbki.**

## 6. ⚠ Gęstość wysypania — źródło większości problemów

- Twoje zdjęcia: **pokrycie ~30–37%**, wymagane dla kształtu **≤15%** (spec-analizy-ksztaltu §2.1).
- Przy tej gęstości **mediana contact_frac ~0,82–0,94** — typowe ziarno styka się na 82–94%
  obwodu. **Tylko ~1–2% ziaren** ma swobodny obrys (spec: 2,3%).
- Skutek: sklejki, cięcia, przerwy-jako-ziarna. **Żaden segmentator nie rozdzieli zlanych ziaren.**
- Software'owo można zostawić tylko swobodne ziarna → ale to ~90 z 8000 (mało).
- **Rozwiązanie: rzadsze wysypanie (tryb `sparse`, ≤15%)** — wtedy blobów w ogóle nie ma,
  a użytecznych ziaren ~1700/zdjęcie. `dense` (50–70%) tylko do barwy/zliczania.

---

## 7. Plan statystycznego odbioru partii (big bag)

Pytanie: ile próbek („przykryw") potrzeba, by przyjąć/odrzucić cały worek.
Docs: reprezentatywność i redukcja są (EN 932-2, spec-przygotowanie §3.2); **statystyki
odbioru brak** — poniżej plan. Standardy: ISO 2859 (atrybutowa), ISO 3951 (zmienna), EN 932-1.

### 7.1 Sedno — dwa poziomy zmienności
1. **Wewnątrz przykrywy** (ziarno-do-ziarna): tysiące ziaren/zdjęcie → %OK znany z ±<1%.
   **Rozwiązane** — precyzja na ziarnach jest świetna.
2. **Między przykrywami / w worku** (segregacja, kieszenie): **to decyduje** o liczbie próbek.
   Zależy od **σ_między** — a to jeszcze niezmierzone.

**Liczba próbek zależy od niejednorodności worka, nie od precyzji na ziarnach.**

### 7.2 Model „kalibruj raz, stosuj na każdym worku"
| co | jak często | zmienia się per worek? |
|---|---|---|
| σ_między (niejednorodność wewnątrz worka) | RAZ na materiał/dostawcę | nie (cecha produktu/pakowania) |
| próg τ + AQL/RQL | RAZ (z ocen eksperta) | nie |
| jakość TEGO worka | każdy worek | tak — to oceniasz 1 pomiarem |

σ_między to **cecha materiału**, nie pojedynczego worka — jak kalibracja termometru:
kalibrujesz raz, potem każdy pacjent = jeden pomiar.

### 7.3 Produkcja: 1–2 pomiary/worek dzięki kompozytowi
Nie mierzy się 15 dawek — **fizycznie uśrednia się je w jedną**:
1. kilkanaście **przyrostów** sondą z różnych miejsc/głębokości worka (EN 932-1),
2. zsyp + wymieszaj → **kompozyt** reprezentuje worek,
3. redukcja kaskadowa → **1 dawka** → zdjęcie.

Compositing uśrednia niejednorodność (wariancja ↓ ~√liczba przyrostów), więc **jeden pomiar**
reprezentuje worek. **Sekwencyjnie (SPRT):** 1 dawka; jeśli granicznie → 2., rzadko 3.

```
big bag → kilkanaście przyrostów → kompozyt → 1 dawka → werdykt
   (graniczny? → 2. dawka / laboratorium)
```

### 7.4 Ile przyrostów/dawek — wzór
`n ≈ ((z_α + z_β) · σ_między / (AQL − RQL))²`

Przy α=β=5% (z≈1,645), AQL 95% vs RQL 92% (odstęp 3 pp):
- worek jednorodny (σ ≈ 2 pp) → **~5**,
- niejednorodny (σ ≈ 5 pp) → **~30**.

Dla kompozytu to liczba **przyrostów**, nie osobnych pomiarów.

### 7.5 Rozruch i utrzymanie
```
RAZ:     kilka worków × parę dawek  → σ_między + progi → PLAN
POTEM:   każdy worek × 1 dawka       → werdykt (+ karta kontrolna SPC w tle)
SPORNE:  → 2. dawka / laboratorium
ZMIANA:  dostawcy/materiału          → przelicz σ_między raz
```
Każdy zmierzony worek dopisuje się do **karty kontrolnej** → dryf wykrywany automatycznie,
bez dodatkowej roboty. Wysiłek jest z przodu (kalibracja), rutyna tania.

To model z spec-operacyjny: system **wspomagający**, ≥90% rozstrzygane na stanowisku,
sporne → laboratorium. Nie potrzeba pewności laboratoryjnej z jednego zdjęcia.

---

## 8. Co dalej (otwarte)
1. **Ustalić co znaczą brzydka/ladna** — bo metryki ziaren ich nie rozróżniają.
2. **Rzadkie wysypanie** (≤15%) → czyste maski, sensowny kształt.
3. **Progi z ocen eksperta** (profil oceny) — bez nich %OK/wtrącenia są nieskalibrowane.
4. **σ_między** — jednorazowa charakteryzacja (kilka worków), żeby ustawić plan odbioru.
5. Opcjonalnie: kalkulator planu odbioru + symulacja karty kontrolnej.
