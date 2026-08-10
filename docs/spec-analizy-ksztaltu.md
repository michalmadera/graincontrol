# Specyfikacja analizy kształtu — dane do wyznaczenia progów

Dokument opisuje **warstwę pomiarową kształtu**: co analiza ma policzyć i zwrócić dla
każdego wykrytego kamienia, tak aby na zbiorze wielu próbek dało się później wyznaczyć
progi akceptacji.

**Nie zawiera żadnych progów i nie definiuje decyzji OK/NOK.** Progi wyznaczone na tych
danych trafiają do systemu operacyjnego jako plik profilu oceny (`spec-operacyjny.md` §6.1),
który niesie też warunki ważności — w przypadku kształtu krytyczne są **model masek
i estymator obwodu** (§3.1, §6), bo ich zmiana przesuwa metrykę o wielokrotność rozrzutu
populacji. Podział na warstwy,
identyfikatory (§3), rekord zdjęcia (§6) i format wyjścia (§10) są **wspólne
z `spec-analizy-barwy.md`** — obie metryki liczy się z tych samych masek, w tym samym
przebiegu, do tej samej tabeli. Ten dokument definiuje wyłącznie to, co dla kształtu
jest inne. Rzeczy inne jest dużo, bo kształt jest wrażliwy na zupełnie inne zakłócenia
niż barwa.

Punktem wyjścia są `wytyczne-ksztalty.md`. Wszystkie liczby przytoczone niżej pochodzą
z pomiaru 8104 instancji na `stones2.png` (`analiza3/out/stones2/`) oraz z kalibracji na
kształtach syntetycznych o znanej geometrii.

---

## 1. Zasada nadrzędna

> Metryka kształtu liczona z maski 2D jest w tej chwili **bardziej właściwością
> segmentacji i zagęszczenia wysypania niż kamienia**. Zadaniem warstwy pomiarowej jest
> to zmierzyć i zapisać, a nie ukryć.

Trzy pomiary, z których wynika cała reszta dokumentu:

**1. Idealne koło nie daje kolistości 1,0.** Syntetyczny dysk o średnicy 34 px — czyli
dokładnie tyle, ile mierzy tu kamień — daje `4πA/P²` = **0,845**, `solidity` = 0,959,
`convexity` = 0,942. Powód: `arcLength` na konturze pikselowym zawyża obwód o 5–6%,
a kolistość zależy od kwadratu obwodu. Skala metryki nie zaczyna się w 1,0 i nie jest
liniowa względem wielkości obiektu.

**2. Wybór estymatora obwodu przesuwa całą skalę.** Ten sam idealny dysk d=34 px:

| estymator obwodu | zmierzony obwód | kolistość `4πA/P²` |
|---|---|---|
| `arcLength` na konturze pikselowym | 112,6 | **0,845** |
| `arcLength` po `approxPolyDP(ε=1,0)` | 105,6 | **0,961** |
| kontur wygładzony średnią ruchomą (k=5) | 103,3 | **1,003** |
| prawda geometryczna (π·d) | 106,4 | 1,000 |

Różnica 0,845 vs 1,003 to **dwie różne metryki pod jedną nazwą**, a różnica między nimi
jest ponad dwukrotnie większa niż całe międzykamienne odchylenie standardowe (0,074).

**3. Zagęszczenie wysypania decyduje bardziej niż materiał.** Mediana `contact_frac`
w tym kadrze wynosi **0,868** — typowy kamień ma 87% obwodu w styku z sąsiadem, więc
mierzy się obrys wycięty przez sąsiadów, a nie obrys kamienia:

| `contact_frac` | n | kolistość | AR | solidity | średnica ekw. |
|---|---|---|---|---|---|
| 0,0–0,2 | 368 | **0,827** | 1,348 | 0,976 | 40,1 px |
| 0,2–0,4 | 423 | 0,800 | 1,320 | 0,967 | 38,0 px |
| 0,4–0,6 | 679 | 0,770 | 1,360 | 0,957 | 36,5 px |
| 0,6–0,8 | 1551 | 0,740 | 1,412 | 0,947 | 34,6 px |
| 0,8–1,0 | 4948 | **0,722** | 1,436 | 0,941 | 32,8 px |

Rozpiętość kolistości między kamieniem swobodnym a zatłoczonym wynosi **0,105**, przy
międzykamiennym odchyleniu standardowym **0,074**. Efekt przysłonięcia jest 1,4 razy
większy niż cały rozrzut populacji. Korelacja kolistości z `contact_frac` to **−0,40** —
najsilniejsza spośród wszystkich zmierzonych kowariat.

Stąd cztery konsekwencje dla schematu danych:

1. **Estymator obwodu jest parametrem specyfikacji, nie implementacji.** Zapisywane są
   wszystkie trzy warianty, a nie jeden „wybrany w kodzie".
2. **`contact_frac` jest polem obowiązkowym**, a nie diagnostycznym dodatkiem. Bez niego
   nie da się odróżnić progu separującego materiał od progu separującego gęstość wysypania.
3. **Podłoga pomiarowa metryki jest zapisywana razem z pomiarem** — dla każdego kamienia
   wartość, jaką dałby idealny dysk o tej samej wielkości i przy tym samym estymatorze.
4. **Kształt wymaga innej akwizycji niż barwa** — rzadszego wysypania. To jest jedyne
   miejsce, w którym te dwie specyfikacje rozjeżdżają się na poziomie stanowiska (§2).

---

## 2. Kontrakt akwizycji dla kształtu

Wszystkie wymagania z `spec-analizy-barwy.md` §2 obowiązują bez zmian (zamrożone
parametry, weryfikacja metadanych, archiwum RAW). Kształt dokłada jedno wymaganie,
którego barwa nie ma:

### 2.1 Gęstość wysypania

Zmierzony udział kamieni o swobodnym obrysie w zależności od lokalnego pokrycia kadru
(okno 5 średnic, ten sam kadr):

| lokalne pokrycie | n | `contact_frac ≤ 0,2` | `contact_frac = 0` |
|---|---|---|---|
| 0–15 % | 62 | **98,4 %** | **85,5 %** |
| 15–30 % | 163 | 70,6 % | 42,3 % |
| 30–45 % | 219 | 39,7 % | 17,4 % |
| 45–60 % | 388 | 17,8 % | 4,1 % |
| 60–75 % | 675 | 5,2 % | 0,7 % |
| > 75 % | 6462 | 0,1 % | 0,0 % |

Obecny kadr ma pokrycie **62,5 %**. W całym zdjęciu tylko **2,3 % kamieni (182 z 7969)**
ma w pełni swobodny obrys. Zbieranie danych do progów kształtu przy takim zagęszczeniu
oznacza, że 97,7 % pomiarów opisuje ułożenie, a nie materiał.

**Wymaganie: dla kształtu materiał wysypywany jest w warstwie o pokryciu ≤ 15 %.**
Przy tym pokryciu w kadrze 4056×3040 mieści się ~2000 kamieni, z czego ~1700 ma
całkowicie swobodny obrys — czyli jedno zdjęcie daje więcej użytecznych pomiarów
kształtu niż obecne gęste zdjęcie, mimo czterokrotnie mniejszej liczby kamieni w kadrze.

To jest **osobny tryb akwizycji** (`pour_mode`), a nie inne ustawienie kamery. Program
akwizycji (`spec-akwizycji.md`) musi go rozróżniać, zapisywać w rekordzie ujęcia
i pilnować, żeby próbki zebrane w trybie gęstym nie trafiły do puli kalibracyjnej kształtu.

| `pour_mode` | pokrycie | do czego |
|---|---|---|
| `dense` | 50–70 % | barwa, granulometria zgrubna, wydajność zliczania |
| `sparse` | ≤ 15 % | **kształt**, granulometria dokładna, walidacja masek |

Uwaga: rzadkie wysypanie pomaga też barwie. Na pełnej populacji korelacja L\* z
`contact_frac` wynosi **+0,39** — czyli więcej niż z polem kamienia (+0,14).
Cieniowanie od sąsiadów jest dla barwy silniejszym zakłóceniem, niż zakładała
`spec-analizy-barwy.md` §5.4. Tryb `sparse` jest więc korzystny dla obu metryk;
tryb `dense` pozostaje potrzebny wyłącznie tam, gdzie badanym zjawiskiem jest samo
zagęszczenie.

---

## 3. Definicja obrysu pomiarowego

Odpowiednik §4 specyfikacji barwy. Tam sporny był zbiór pikseli; tu sporne jest to,
**czym jest obwód**.

### 3.1 Trzy estymatory obwodu — wszystkie liczone i zapisywane

| nazwa | definicja | zachowanie na idealnym dysku d=34 px |
|---|---|---|
| `P_chain` | `arcLength` na konturze `CHAIN_APPROX_NONE` | zawyża o 5,8 % → kolistość 0,845 |
| `P_poly` | `arcLength` po `approxPolyDP(ε=1,0)` | zaniża o 0,8 % → kolistość 0,961 |
| `P_smooth` | kontur wygładzony średnią ruchomą po współrzędnych, k=5 | zaniża o 2,9 % → kolistość **1,003** |

Wariantem podstawowym jest **`P_smooth`**, bo jako jedyny sprowadza idealne koło do 1,0
przy wielkości kamienia z tego stanowiska, czyli metryka odzyskuje deklarowaną
interpretację. Pozostałe dwa są zapisywane, żeby dało się odtworzyć wyniki liczone
wcześniej (`analiza2/`, `analiza3/measure.py` używają `P_chain`) i żeby wybór dało się
zrewidować bez powtarzania pomiarów.

Zawyżenie obwodu przez `P_chain` jest **stałe względem skali** (mierzone: +5,1 % przy
r=8, +5,8 % przy r=17, +5,0 % przy r=40, +5,3 % przy r=200), więc jest to błąd
systematyczny metody, a nie efekt małych obiektów.

### 3.2 Konwencja kolistości — rozstrzygnięcie

`wytyczne-ksztalty.md` §1 podaje wzór `C = P²/(4πA)`, ale opis słowny („wartość zbliżona
do 1 oznacza kształt zbliżony do koła, niższe wartości wskazują na kształt wydłużony")
i próg `C ≥ 0,70` odpowiadają konwencji odwrotnej. Przy wzorze z dokumentu wartości są
zawsze ≥ 1 i **próg 0,70 jest nieosiągalny dla żadnego kształtu**.

Rozstrzygnięcie: zapisywane są obie wielkości, pod jednoznacznymi nazwami i z jawnie
podaną interpretacją, a dokument wytycznych wymaga poprawki.

| kolumna | wzór | interpretacja |
|---|---|---|
| `circularity_4piA_P2` | 4πA/P² | 1,0 = koło, **mniej = mniej okrągłe** |
| `circularity_P2_4piA` | P²/(4πA) | 1,0 = koło, **więcej = mniej okrągłe** |

Iloczyn obu musi wynosić dokładnie 1 — to jest kryterium odbioru (§9).

### 3.3 Pole powierzchni

Rozróżniane są dwie wielkości, bo nie są równe i mieszanie ich jest cichym źródłem błędu:

- `area_px` — liczba pikseli maski; wielkość granulometryczna, z niej liczona jest
  średnica ekwiwalentna;
- `contour_area_px` — pole wielokąta konturu; z niego liczone są kolistość i solidity,
  żeby pole i obwód pochodziły z tego samego obiektu geometrycznego.

### 3.4 Podłoga pomiarowa jako kolumna

Dla każdego kamienia zapisywana jest wartość, jaką **idealny dysk o tej samej średnicy
ekwiwalentnej** dałby przy tym samym estymatorze obwodu: `circ_floor_4piA_P2`,
`solidity_floor`, `convexity_floor`. Wartości pochodzą z tablicy kalibracyjnej
generowanej raz przez skrypt kalibracyjny i zapisywanej razem z wynikami.

Powód: podłoga zależy od wielkości obiektu w sposób niemonotoniczny i nieprzewidywalny
z wzoru. Zmierzone dla `P_chain`: d=10,2 px → 0,763; d=15,8 → 0,800; d=20,1 → 0,832;
d=23,7 → 0,859; d=33,9 → 0,845; d=50,0 → 0,874; d=160 → 0,889. Warstwa 3 może dzięki
temu pracować na kolistości znormalizowanej `circ / circ_floor(d)`, co usuwa zależność
podłogi od wielkości, nie ruszając sygnału materiałowego.

### 3.5 Szum własny pomiaru

Zmierzone przez przesuwanie idealnego kształtu po siatce pikseli, przy **zerowej zmianie
geometrii**:

| metryka | rozstęp | sd |
|---|---|---|
| kolistość (dysk d=34 px, przesunięcie subpikselowe) | 0,845–0,911 = **0,066** | 0,0083 |
| solidity | 0,960–0,989 | 0,0033 |
| convexity | 0,943–0,968 | 0,0035 |
| AR | 1,000–1,015 | 0,0039 |
| kolistość (elipsa AR=1,5 obracana co 5°) | 0,811–0,853 | 0,0120 |
| AR (elipsa AR=1,5 obracana) | 1,522–1,569 | 0,0124 |

Szum siatki (sd 0,008) to ~11 % międzykamiennego odchylenia standardowego kolistości
(0,074) — jest do przyjęcia. Problemem nie jest szum, tylko obciążenie: skala nie zaczyna
się tam, gdzie mówi dokumentacja.

---

## 4. Rekord pojedynczego kamienia

Rozszerza rekord z `spec-analizy-barwy.md` §5 o kolumny kształtu. Jeden wiersz na kamień,
ta sama tabela `stones.parquet` — kształt i barwa pochodzą z tej samej maski i nie ma
powodu ich rozdzielać.

### 4.1 Wielkości podstawowe
| kolumna | opis |
|---|---|
| `area_px` | liczba pikseli maski |
| `contour_area_px` | pole wielokąta konturu |
| `convex_area_px` | pole otoczki wypukłej |
| `equiv_diameter_px` | 2√(`area_px`/π) |
| `P_chain`, `P_poly`, `P_smooth` | trzy estymatory obwodu (§3.1) |
| `P_hull` | obwód otoczki wypukłej |
| `n_contour_points` | liczba punktów konturu — miara rozdzielczości obrysu |

### 4.2 Metryki kształtu
Dla **każdego** z trzech estymatorów obwodu, z przyrostkiem `_chain` / `_poly` / `_smooth`:

| kolumna | wzór | uwagi |
|---|---|---|
| `circularity_4piA_P2_*` | 4πA/P² | wariant podstawowy: `_smooth` |
| `circularity_P2_4piA_*` | P²/(4πA) | §3.2 |
| `convexity_*` | `P_hull`/P | chropowatość obrysu; mniej wrażliwa niż solidity |

Bez zależności od estymatora obwodu:

| kolumna | wzór / źródło | po co |
|---|---|---|
| `solidity` | `contour_area_px` / `convex_area_px` | wgłębienia, wklęsłości |
| `aspect_ratio_ellipse` | oś większa / mniejsza z `fitEllipse` | zgodność z `wytyczne-ksztalty.md` |
| `aspect_ratio_feret` | Feret max / Feret min | **stabilniejszy przy kształtach kanciastych** |
| `feret_max`, `feret_min`, `feret_90` | suwmiarka co 2°, oraz szerokość prostopadła do Fereta maks. | |
| `major_axis_px`, `minor_axis_px`, `orientation_deg` | `fitEllipse` | orientacja do wykrycia preferowanego ułożenia |
| `roundness` | 4A/(π·`feret_max`²) | odporna na chropowatość, w przeciwieństwie do kolistości |
| `elongation` | 1 − `feret_min`/`feret_max` | |
| `extent` | `area_px` / pole bboxa | |
| `rectangularity` | `contour_area_px` / pole `minAreaRect` | dla materiału kanciastego lepsza niż solidity |
| `minrect_w`, `minrect_h` | wymiary `minAreaRect` | trzeci, niezależny estymator wydłużenia |
| `eccentricity` | z momentów drugiego rzędu | niezależny od dopasowania elipsy |

Trzy niezależne estymatory wydłużenia (elipsa, Feret, `minAreaRect`) są celowe:
zmierzone obciążenie dopasowania elipsy przy AR=2,0 wynosi **+6,4 %** (2,127 zamiast
2,000), Feret **+3,8 %** (2,076). Przy AR=3,0 odpowiednio +11,5 % i +6,2 %. Który
estymator jest właściwy dla tego materiału, rozstrzygnie warstwa 3 — pod warunkiem,
że wszystkie trzy zostaną zebrane.

### 4.3 Podłoga pomiarowa
`circ_floor_4piA_P2_chain`, `circ_floor_4piA_P2_poly`, `circ_floor_4piA_P2_smooth`,
`solidity_floor`, `convexity_floor` — patrz §3.4. Plus `floor_table_id` wskazujący
wersję tablicy kalibracyjnej.

### 4.4 Kowariaty zakłócające — obowiązkowe

Wspólne z rekordem barwy, ale **wagi są inne** i dlatego wymagają osobnego komentarza:

| kolumna | zmierzona korelacja z kolistością | dlaczego kluczowa |
|---|---|---|
| `contact_frac` | **−0,40** | najsilniejszy zakłócacz; obrys wycięty przez sąsiadów |
| `n_contact` | −0,29 | j.w. |
| `local_coverage` | (pochodna `contact_frac`) | lokalne pokrycie w oknie 5 średnic — kontrola trybu wysypania (§2.1) |
| `area_px` | +0,27 | podłoga pomiarowa zależy od wielkości (§3.4) |
| `r_norm` | +0,27 | pozycja w kadrze: perspektywa i rozmycie poza osią |
| `touches_border` | — | obrys ucięty krawędzią kadru |
| `n_contour_points` | — | zbyt mało punktów = obwód niemierzalny |

Korelacja z `r_norm` (+0,27) zasługuje na uwagę: kamienie przy brzegu kadru mierzą się
jako mniej okrągłe. Przyczyną może być perspektywa (obiekty poza osią optyczną widziane
pod kątem), spadek ostrości poza osią albo mniejsze zagęszczenie przy brzegu wysypanej
kupki, skorelowane z `contact_frac`. **Rozdzielenie tych trzech przyczyn wymaga zdjęcia
w trybie `sparse` i nie jest w tej chwili rozstrzygnięte** — dlatego `r_norm` jest polem
obowiązkowym, a nie diagnostycznym.

### 4.5 Flaga ważności — ostrzejsza niż dla barwy

```
valid_shape = NOT touches_border
              AND equiv_diameter_px >= 20
              AND n_contour_points >= 40
              AND contact_frac <= contact_frac_max
```

`contact_frac_max` jest parametrem zapisywanym do `capture.json` jako łańcuch, tak samo
jak `valid_color_rule`. Wartość startowa **0,2** — przy niej metryki są jeszcze bliskie
wartościom dla kamieni w pełni swobodnych (kolistość 0,827 vs 0,812 w przedziale 0–0,2).

Próg `equiv_diameter_px ≥ 20` wynika z §3.4: poniżej 20 px podłoga pomiarowa kolistości
spada poniżej 0,83 i szybko rośnie jej wrażliwość na pojedyncze piksele.

Kamienie nieważne **pozostają w zbiorze** z podaną przyczyną. Przy obecnym trybie `dense`
`valid_shape` odrzuci ~95 % instancji — i właśnie ta liczba jest komunikatem, że tryb
akwizycji jest nieodpowiedni, a nie że coś jest zepsute.

---

## 5. Rekord próbki

Jak w `spec-analizy-barwy.md` §7, liczony z kamieni o `valid_shape = true`, z pełnym
zestawem percentyli (P01…P99), plus pozycje specyficzne dla kształtu:

| grupa | zawartość |
|---|---|
| liczności | `n_stones`, `n_valid_shape`, `n_invalid` z rozbiciem na przyczynę |
| kształt | pełny rozkład dla każdej metryki z §4.2, w wariancie podstawowym i w `_chain` (do porównań wstecz) |
| kształt znormalizowany | rozkład `circularity / circ_floor` — metryka pozbawiona zależności od wielkości |
| granulometria | percentyle `equiv_diameter_px`, `feret_max`, `feret_min`; `d10`/`d50`/`d90` w mm, jeśli `mm_per_px` pochodzi z pomiaru wzorca |
| orientacja | rozkład `orientation_deg` oraz test jednorodności — niejednorodność oznacza, że kamienie układają się preferencyjnie, więc mierzone AR jest zaniżone |
| kowariaty | `pour_mode`, pokrycie kadru, mediana `contact_frac`, mediana `local_coverage`, udział kamieni swobodnych |
| kontrola biasu | `corr_circ_contact_frac`, `corr_circ_area`, `corr_circ_r_norm`, mediana kolistości w podziale na kwintyle `contact_frac` |

Rozkład orientacji jest pozycją, której `wytyczne-ksztalty.md` nie ma, a która jest
konieczna: metryka 2D mierzy **rzut** kamienia. Płaski kamień leżący płasko wygląda
okrągło, ten sam kamień oparty o sąsiada wygląda wydłużony. Jeżeli w jednej próbce
kamienie układają się losowo, a w innej preferencyjnie, ich AR są nieporównywalne —
a bez pomiaru rozkładu orientacji nie da się tego zauważyć.

---

## 6. Zależność od algorytmu segmentacji

Ten sam obraz, ta sama analiza, dwa algorytmy masek (`analiza2/`):

| algorytm | mediana `circularity_4piA_P2` |
|---|---|
| watershed h=25 | **0,428** |
| cellpose cyto3 (cztery konfiguracje) | 0,708 – 0,712 |

Różnica **0,28** to 3,8-krotność międzykamiennego odchylenia standardowego. Dla porównania
różnica między czterema konfiguracjami cellpose to 0,004 — czyli w granicach szumu.

Wniosek: **próg kształtu jest ważny wyłącznie dla tej wersji modelu masek, dla której
został wyznaczony.** Zmiana modelu — w tym planowane przejście z cellpose na model
dedykowany — unieważnia progi kształtu tak samo, jak zmiana pliku strojenia unieważnia
progi barwy.

Wymagania z tego wynikające:

1. `mask_model` i `mask_params` są częścią klucza każdego progu, nie tylko metadanymi.
2. Przy wymianie modelu obowiązuje **ujęcie pomostowe**: ten sam zbiór zdjęć przepuszczony
   przez stary i nowy model, z wyznaczeniem przesunięcia rozkładu każdej metryki. Bez tego
   nie da się przenieść progów i całą kalibrację trzeba powtórzyć.
3. Zbiór walidacyjny masek z ręcznie poprawionymi obrysami (Label Studio, patrz
   `analiza2/wnioski.md`) jest **wymagany**, nie opcjonalny — to jedyne odniesienie,
   względem którego da się stwierdzić, czy nowy model zmienia metryki w dobrą stronę.

---

## 7. Protokół zbierania danych

Etapy A–F z `spec-analizy-barwy.md` §8 obowiązują, z trzema modyfikacjami:

- **Wszystkie etapy w trybie `sparse`** (§2.1). Materiał zebrany w trybie `dense`
  nie wchodzi do puli kalibracyjnej kształtu.
- **Etap B (powtarzalność ułożenia) jest dla kształtu ważniejszy niż dla barwy.**
  Kamień przy każdym wysypaniu ląduje w innej orientacji, a mierzy się jego rzut.
  σ_layout dla AR i kolistości będzie istotnie większe niż dla L\* i to ono, a nie
  szum pomiaru, wyznacza dolny kres każdego progu kształtu.
- **Nowy etap G — kalibracja na kształtach wzorcowych.** Sfotografowanie obiektów
  o znanej geometrii (kulki szklane lub łożyskowe o znanej średnicy, wycięte krążki
  i elipsy) w tej samej scenie. Daje bezpośredni pomiar podłogi i obciążenia całego
  toru — obiektywu, ISP, segmentacji i metryki naraz — czego kalibracja syntetyczna
  z §3.4 nie obejmuje, bo pomija optykę i segmentację.

Etap G jest tani i rozstrzyga pytanie, na które inaczej nie ma odpowiedzi: ile z różnicy
między 0,845 (dysk syntetyczny) a 0,738 (zmierzony kamień) to kształt kamienia, a ile
rozmycie obiektywu i błąd konturu z cellpose.

---

## 8. Wymagania wobec procedury wyznaczania progów

Uzupełnienie `spec-analizy-barwy.md` §9 o punkty specyficzne dla kształtu:

1. **Progi odnoszą się do znormalizowanej metryki albo do jawnie podanej podłogi.**
   Zapis „C ≥ 0,70" bez podania estymatora obwodu i modelu masek jest niepełny w stopniu
   uniemożliwiającym implementację.
2. **Próg musi przekraczać σ_layout z etapu B**, nie szum pomiaru. Szum siatki (sd 0,008)
   jest o rząd wielkości mniejszy niż zmienność wynikająca z przeturlania kamienia.
3. **Kontrola, czy próg nie separuje zagęszczenia.** Obowiązkowy raport: rozkład
   `contact_frac` w klasie zaakceptowanej i odrzuconej. Jeśli się różnią, próg mierzy
   ułożenie.
4. **Rozstrzygnięcie, która metryka wydłużenia obowiązuje** (elipsa / Feret /
   `minAreaRect`) — na danych, nie z góry.
5. **Odniesienie do normy, jeśli odbiorca ją stosuje.** Wskaźniki płaskości i kształtu
   z EN 933-3/933-4 są pomiarem 3D suwmiarką na sitach; metryka 2D jest ich przybliżeniem
   i przelicznik trzeba wyznaczyć empirycznie na materiale zmierzonym oboma metodami.
   Bez tego progi z obrazu nie dają się zestawić ze specyfikacją zakupową.

Odniesienie: progi z `wytyczne-ksztalty.md` §3 zastosowane wprost do zmierzonych danych
(8104 kamienie, konwencja `4πA/P²`, estymator `P_chain`):

| kryterium | wynik |
|---|---|
| C ≥ 0,70 | 68,9 % kamieni OK |
| AR ≤ 1,50 | 61,1 % kamieni OK |
| S ≥ 0,90 | 87,3 % kamieni OK |
| wszystkie trzy naraz | **52,6 %** przy wymaganych 95 % |
| Median C ≥ 0,80 | zmierzone **0,738** — niespełnione |
| Median AR ≤ 1,30 | zmierzone **1,411** — niespełnione |
| Median S ≥ 0,95 | zmierzone **0,947** — niespełnione |

Partia zostałaby odrzucona pięcioma kryteriami naraz. Te liczby nie mówią nic
o materiale — mówią, że progi zostały zapisane przed pierwszym pomiarem.

---

## 9. Kryteria odbioru warstwy pomiarowej kształtu

| kryterium | sposób sprawdzenia |
|---|---|
| zgodność konwencji | `circularity_4piA_P2 × circularity_P2_4piA = 1` dla każdego wiersza |
| poprawność podłogi | syntetyczne dyski d = 10…160 px przepuszczone przez pipeline odtwarzają tablicę z §3.4 |
| kalibracja estymatorów | idealny dysk d=34 px daje `circularity_*_smooth` w przedziale 1,00 ± 0,01 |
| odporność na siatkę | ten sam kształt przesuwany subpikselowo: sd kolistości ≤ 0,01 |
| odtwarzalność Fereta | elipsa o znanym AR odtworzona z błędem ≤ 5 % dla AR ≤ 2 |
| kompletność kowariat | każdy rekord ma wypełnione `contact_frac`, `local_coverage`, `r_norm`, `n_contour_points` |
| determinizm | ten sam wejściowy `labels.npy` → bitowo identyczne wyjście |
| wykrycie trybu wysypania | zdjęcie w trybie `dense` daje `n_valid_shape` < 10 % i ostrzeżenie w rekordzie próbki |

---

## 10. Czego ten dokument nie rozstrzyga

- Wartości progów — to przedmiot badania z §7–8.
- Który estymator wydłużenia jest właściwy dla tego materiału.
- Czy metrykę należy normalizować podłogą, czy raportować surowo i uwzględniać podłogę
  dopiero w regule progowej — obie drogi są poprawne, wybór wymaga danych z etapu G.
- Źródła korelacji kolistości z pozycją w kadrze (+0,27): perspektywa, spadek ostrości
  poza osią, czy skorelowana z brzegiem kupki gęstość wysypania. Rozstrzyga to zdjęcie
  w trybie `sparse` z materiałem rozłożonym równomiernie po całym kadrze.
- Czy do granulometrii wystarczy średnica ekwiwalentna, czy potrzebne są wymiary
  suwmiarkowe zestawialne z analizą sitową.
- Przelicznika między metryką obrazową a wskaźnikami z EN 933-3/933-4.
