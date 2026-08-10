# Specyfikacja analizy pomiarowej — dane do wyznaczenia progów

Dokument opisuje **warstwę pomiarową**: co analiza ma policzyć i zwrócić dla każdego
zdjęcia, tak aby na zbiorze wielu próbek dało się później wyznaczyć progi akceptacji.

**Ten dokument nie zawiera żadnych progów i nie definiuje decyzji OK/NOK.**
To jest celowe. Progi są przedmiotem osobnego badania i muszą powstać z danych, a nie
poprzedzać ich zebranie. Podział na warstwy:

| warstwa | co robi | kiedy powstaje |
|---|---|---|
| **1. Akwizycja** | zdjęcie na zamrożonych parametrach + metadane (`spec-akwizycji.md`) | teraz |
| **2. Pomiar** (ten dokument) | maski → wartości liczbowe na kamień i na próbkę | teraz |
| **3. Kalibracja progów** | rozkłady z wielu próbek → **plik profilu oceny** | badanie |
| **4. Decyzja** | profil oceny stosowany w ruchu (`spec-operacyjny.md`) | produkcja |

Produktem warstwy 3 jest plik JSON o strukturze zdefiniowanej w `spec-operacyjny.md` §6.1.
Plik niesie progi, reguły klasyfikacji kamienia do klasy wtrącenia oraz **warunki ważności**:
identyfikator profilu akwizycji, model masek, wersję pipeline'u i format zdjęcia. System
operacyjny odmawia wczytania profilu, którego warunki ważności nie zgadzają się z jego
konfiguracją — to jest mechanizm, który pilnuje, żeby progi wyznaczone tutaj opisywały
to, co tam jest mierzone.

Warstwa 2 musi być zamrożona i wersjonowana **zanim** ruszy warstwa 3, bo każda zmiana
definicji pomiaru unieważnia zebrane dane kalibracyjne.

---

## 1. Zasada nadrzędna

> Analiza zwraca **wartości i kowariaty**, nie oceny. Wszystko, czego nie da się
> odtworzyć z zapisanego rekordu, musi być zapisane w rekordzie.

Trzy konsekwencje, które przesądzają o schemacie danych:

1. **Rekordy pojedynczych kamieni są zapisywane w całości.** Ze statystyk próbki nie da
   się odzyskać rozkładu, a progi wyznacza się z rozkładu. Agregaty zawsze można
   przeliczyć z rekordów; odwrotnie nie.
2. **Każdy pomiar barwy jest zapisywany razem z kowariatami zakłócającymi**
   (pole, przysłonięcie, pozycja w kadrze, jakość maski). Bez nich nie da się odróżnić
   progu, który separuje materiał, od progu, który separuje geometrię — patrz §7.
3. **ΔE i wszystkie wielkości względem wzorca są wielkościami pochodnymi.** Warstwa 2
   zapisuje surowe L\*a\*b\*. ΔE liczy się w warstwie 3, gdy wzorzec jest już znany,
   i można je przeliczyć wstecz dla całego zbioru po zmianie wzorca.

---

## 2. Kontrakt akwizycji (warunek ważności pomiaru)

### 2.1 Weryfikacja metadanych — twarda

Analiza **odrzuca zdjęcie**, jeśli metadane nie potwierdzają zamrożenia toru.
Sprawdzane pola z JSON-a `rpicam-still`:

| pole | wymaganie |
|---|---|
| `ExposureTime` | równe zadanemu, tolerancja ±1% |
| `AnalogueGain` | równe zadanemu, tolerancja ±1% |
| `DigitalGain` | **1,000 ±0,01** — wartość różna od 1 oznacza, że ISP kompensował ekspozycję i skala jasności jest przesunięta |
| `ColourGains` | równe zadanym, tolerancja ±1% |
| `ColourCorrectionMatrix` | **identyczna we wszystkich ujęciach sesji** — patrz 2.3 |
| `Lux` | zapisywane, bez progu — służy jako detektor zmiany oświetlenia w czasie |

### 2.2 Parametry ISP do zamrożenia

Stan obecny (`photoNewParam_final.py`): zamrożone są `--shutter 65000`, `--gain 1.0`,
`--awbgains 2.36,2.19`. Nie są zamrożone parametry ISP. Wartości domyślne
(zweryfikowane w `core/options.cpp` rpicam-apps) i wymagane ustawienia:

| opcja | domyślnie | ustawić na | czy zmienia dzisiejszy obraz |
|---|---|---|---|
| `--sharpness` | **1.0 = „normal sharpening"** | **0** | **tak** — wyostrzanie jest obecnie włączone |
| `--denoise` | `auto` → dla stilla rozwija się do **`cdn_hq`** | **`off`** | **tak** — najagresywniejszy wariant colour denoise jest obecnie aktywny |
| `--saturation` | 1.0 (neutralne) | 1.0 | nie — zamek na przyszłość |
| `--contrast` | 1.0 (neutralne) | 1.0 | nie — zamek na przyszłość |
| `--brightness` | 0 (neutralne) | 0 | nie — zamek na przyszłość |

`--denoise` steruje dwoma niezależnymi filtrami: SDN (spatial, na danych Bayera) i CDN
(colour, uśrednianie chromy w domenie YUV). Mapowanie wartości w rpicam-apps:
`off` → `NoiseReductionModeOff`, `cdn_off` → `Minimal`, `cdn_fast` → `Fast`,
`cdn_hq` → `HighQuality`; `auto` podstawia `cdn_hq` dla zdjęć i `cdn_fast` dla wideo.
Dla pomiaru barwy krytyczny jest CDN, bo **przestrzennie uśrednia chromę** — miesza
a\*/b\* między sąsiadującymi kamieniami i między kamieniem a tłem, czyli degraduje
dokładnie mierzony sygnał. Zapas na wyłączenie jest duży: zmierzony szum własny pomiaru
(dwie losowe połówki pikseli tego samego kamienia) to mediana ΔE00 = 0,21, a mediana
barwy liczona jest z 500–900 pikseli. Po zmianie test połówkowy należy powtórzyć —
kryterium: mediana ΔE00 < 1,0.

`--sharpness 0` dotyczy **cyfrowego wyostrzania krawędzi w ISP**, nie ostrości optycznej
obiektywu (ta pozostaje ustawiona i zablokowana mechanicznie). Halo od wyostrzania
zawyża jasność pikseli przybrzeżnych; erozja maski (§4) to łagodzi, ale nie usuwa.
Na `stones1.png` próba wykrycia halo dała wynik niejednoznaczny: ze 183 profili krawędzi
kamień→tło (skok 88 DN) po jasnej stronie **nie ma przestrzelenia**, po ciemnej jest
dołek 2,7 DN (3,1% skoku) wracający przez ~10 px — nieodróżnialny od naturalnego cienia
kontaktowego. Rozstrzyga wyłącznie porównanie A/B tej samej sceny przy `--sharpness 0`
i `1.0`; należy je wykonać i wynik zapisać.

Uwaga wtórna: wyłączenie denoise zmienia teksturę, więc parametry i jakość masek
(§4, `analiza2/`) trzeba przeliczyć na nowym materiale — mediana pola i kolistość mogą
się przesunąć.

### 2.3 Plik strojenia — decyzja z konsekwencjami

Plik strojenia definiuje **cały ISP**: krzywą tonalną, macierze korekcji barwy (CCM),
korekcję winietowania (ALSC), parametry wyostrzania i denoise. Bez `--tuning-file`
libcamera używa domyślnego `imx477.json` — tak powstał `stones1.png`. Porównanie
z wariantem pomiarowym (zweryfikowane w repozytorium libcamera, gałąź `vc4`):

| blok | `imx477.json` (używany teraz) | `imx477_scientific.json` |
|---|---|---|
| `rpi.sharpen` | threshold 0,75 / limit 0,5 / strength 1,0 | **identyczny** |
| `rpi.contrast` → `ce_enable` | 1 — wzmocnienie kontrastu włączone | **0 — wyłączone** |
| krzywa gamma, wejście 25% | wyjście **62,0%** | wyjście **48,6%** (Rec.709, odcinek liniowy o nachyleniu 4,5) |
| `rpi.ccm` | 6 temperatur barwowych | **19 temperatur (2000–8600 K)**, rekalibrowane |
| `rpi.alsc` (winietowanie) | **obecny — korekcja działa** | **nieobecny — korekcji nie ma** |
| `rpi.sdn` / `rpi.cdn` | sdn obecny, cdn brak | tak samo |

Trzy konsekwencje wiążące dla tej specyfikacji:

1. **Plik scientific nie wyłącza wyostrzania ani nie ma jednostkowej macierzy kolorów.**
   Blok `rpi.sharpen` jest w obu plikach identyczny — wyostrzanie zdejmuje wyłącznie
   `--sharpness 0`. CCM nie jest jednostkowa, tylko skalibrowana na 19 temperaturach,
   i to jest jej zaleta. (Prostuje to opis w `rekomendacja.md`.)
2. **Zmiana pliku strojenia przesuwa całą skalę jasności.** Kamienie leżą przy
   DN ≈ 130–150, czyli 51–59% zakresu — dokładnie tam, gdzie obie krzywe różnią się
   najsilniej. Po przełączeniu obraz pociemnieje, `--shutter` trzeba dobrać od nowa,
   a dotychczasowa baza (mediana L\* ≈ 62) przestaje być porównywalna.
3. **Plik scientific nie zawiera bloku ALSC, czyli wyłącza korekcję winietowania.**
   Obecna, bardzo płaska charakterystyka pola oświetlenia (rozpiętość P98 L\* tylko
   3,3 jedn., §6) jest częściowo zasługą ALSC z pliku domyślnego. Po przejściu na
   scientific winietowanie wróci i **korekcja flat-field przestaje być opcjonalna**
   (§12). Test weryfikujący: zdjęcie równomiernie oświetlonej białej powierzchni
   z każdym plikiem strojenia, porównanie rogu ze środkiem.

Rekomendowana kolejność: przejść na `imx477_scientific.json` **przed** startem
zbierania danych z §8, razem z flat-fieldem i ponownym doborem `--shutter`. Zmiana
pliku strojenia w trakcie badania unieważnia wszystkie wcześniej zebrane wartości.
Ścieżka zależy od modelu: `/usr/share/libcamera/ipa/rpi/vc4/` (Pi 4 i starsze) albo
`/usr/share/libcamera/ipa/rpi/pisp/` (Pi 5) — obecność pliku należy sprawdzić na
urządzeniu.

Do czasu przejścia zmierzone L\*a\*b\* należy traktować jako **skalę przyrządową**,
nie kolorymetryczną — porównywalną wyłącznie w obrębie tego stanowiska i tej wersji
strojenia.

`ColourCorrectionMatrix` z metadanych wchodzi do kontroli (2.1), bo plik scientific
wybiera CCM z 19 wariantów na podstawie oszacowanej temperatury barwowej. Przy
zamrożonych `awbgains` powinno to być deterministyczne — ale to jest do zweryfikowania
pomiarem, nie do założenia.

### 2.4 Archiwum RAW — wymagane

Każde zdjęcie do badania progów zapisywane jest **równolegle jako PNG i DNG**
(`--raw`). DNG powstaje przed ISP, więc jest odporny na wszystkie ustawienia z 2.2
i 2.3. Jeśli którekolwiek zamrożenie okaże się złym wyborem, z DNG da się przeliczyć
cały zebrany materiał; z PNG nie da się odzyskać nic. Przy badaniu obliczonym na
dziesiątki próbek jest to warunek odwracalności całego przedsięwzięcia, nie wygoda.

### 2.5 Zapisywane bez automatycznej weryfikacji

Przysłona, pozycja ostrości (zablokowana mechanicznie), identyfikator
lampy/oświetlacza, czas od włączenia oświetlenia, temperatura otoczenia,
wersja `rpicam-apps` i `libcamera`.

### 2.6 Docelowe wywołanie

```
rpicam-still -o out.png --encoding png --width 4056 --height 3040 \
  --tuning-file /usr/share/libcamera/ipa/rpi/vc4/imx477_scientific.json \
  --shutter <dobrać od nowa po zmianie strojenia> --gain 1.0 \
  --awbgains 2.36,2.19 \
  --sharpness 0 --denoise off \
  --saturation 1.0 --contrast 1.0 --brightness 0 \
  --raw \
  --metadata meta.json --metadata-format json
```

---

## 3. Poziomy danych i identyfikatory

```
study  →  batch/dostawa  →  sample (jedno wysypanie materiału)  →  capture (jedno zdjęcie)  →  stone
```

`sample` i `capture` to osobne poziomy celowo: jedna próbka może być sfotografowana
wielokrotnie bez ruszania materiału (powtarzalność ujęcia) i wielokrotnie po ponownym
wysypaniu (powtarzalność ułożenia). Bez tego rozdziału nie da się rozłożyć wariancji
na składowe — a to jest warunek konieczny sensownego progu (§8).

Klucze: `study_id`, `batch_id`, `sample_id`, `capture_id`, `stone_id`
(unikalne w obrębie `capture_id`), `layout_seq` (numer ponownego wysypania w obrębie
`sample_id`), `frame_seq` (numer ujęcia w obrębie `layout_seq`).

---

## 4. Definicja pikseli pomiarowych

Nierozstrzygnięta definicja „pikseli należących do kamienia" jest samodzielnym źródłem
błędu rzędu 1 jednostki L\*, czyli ok. 20% typowego budżetu ΔE. Musi być zapisana w specyfikacji,
a nie w kodzie.

Dla każdej instancji z maski wyznaczamy **trzy warianty zbioru pikseli** i liczymy
statystyki dla każdego z nich:

| wariant | definicja | uzasadnienie |
|---|---|---|
| `raw` | maska instancji bez zmian | odniesienie, pokazuje wpływ jakości maski |
| `er3` | erozja 3×3, przecięta z maską pierwszego planu (Otsu) | kompromis |
| `er5` | erozja 5×5, przecięta z maską pierwszego planu | **wariant podstawowy** |

Zmierzone na `crop_center_512.png` (321 instancji, cellpose cyto3 d=35 cellprob −1):
udział tła wciągniętego do maski 9,4% → 5,1% → 1,5%; rozrzut L\* wewnątrz kamienia
(P95−P5) 26,7 → 14,9 → 9,2; mediana L\* 61,8 → 62,3 → 62,8. Przy erozji 5 px wszystkie
321 instancji zachowuje ≥50 px (mediana 480 px), przy 7 px trzy instancje wypadają —
dlatego 5 px jest górną sensowną granicą dla tej wielkości kamienia (~35 px średnicy).

Warunek ważności pomiaru barwy pojedynczego kamienia: `n_px_er5 ≥ 50`.
Kamienie niespełniające warunku trafiają do zbioru z flagą, nie są usuwane po cichu.

Piksele przesterowane (dowolny kanał ≥ 250 DN) są **liczone i raportowane**, nie
wycinane — ich obecność ma być sygnałem, że ekspozycja wyjechała, a nie ukrytą korektą.
W `stones1.png` takich pikseli jest 0,000%; najjaśniejszy piksel kadru ma L\* = 76,0.

---

## 5. Rekord pojedynczego kamienia

Format zapisu: jeden wiersz na kamień (Parquet lub CSV). Nazewnictwo kolumn barwnych:
`{wariant}_{kanał}_{statystyka}`, np. `er5_L_median`, `raw_b_p95`.

### 5.1 Identyfikacja i pochodzenie
| kolumna | typ | opis |
|---|---|---|
| `study_id`, `batch_id`, `sample_id`, `capture_id`, `stone_id` | str/int | klucze z §3 |
| `mask_model` | str | np. `cellpose-3.1.1.2/cyto3` |
| `mask_params` | str | serializowane parametry (`diameter`, `flow_threshold`, `cellprob_threshold`) |
| `pipeline_version` | str | wersja kodu warstwy 2 |

### 5.2 Barwa — dla wariantów `raw`, `er3`, `er5`, dla kanałów `L`, `a`, `b`
`n_px`, `median`, `mean`, `sd`, `p05`, `p25`, `p75`, `p95`

Do tego, liczone z median wariantu: `{wariant}_C_ab` (√(a\*²+b\*²) — **z pierwiastkiem**;
w `wytyczne-barwy.md` wzór stracił pierwiastek przy eksporcie) oraz
`{wariant}_h_ab` (kąt odcienia, `atan2(b*, a*)` w stopniach).

Przestrzeń: CIELAB, iluminant D65, obserwator 2°, wejście traktowane jako sRGB
(dekodowanie gammy sRGB przed konwersją). Konwersja i jej wersja biblioteczna
zapisywane w rekordzie `capture` — patrz §6.

### 5.3 Geometria (kowariaty barwy **i** jednocześnie dane do progów kształtu)
| kolumna | opis |
|---|---|
| `area_px` | pole maski instancji |
| `perimeter_px` | obwód konturu zewnętrznego |
| `convex_area_px` | pole otoczki wypukłej |
| `equiv_diameter_px` | 2√(A/π) |
| `major_axis_px`, `minor_axis_px` | osie elipsy dopasowanej |
| `circularity_4piA_P2` | 4πA/P² — **1,0 = koło, mniej = mniej okrągłe** |
| `circularity_P2_4piA` | P²/(4πA) — **1,0 = koło, więcej = mniej okrągłe** |
| `aspect_ratio` | major/minor |
| `solidity` | A / A_convex |

Obie definicje kolistości są zapisywane rozłącznie i pod jednoznacznymi nazwami, bo
`wytyczne-ksztalty.md` używa wzoru P²/(4πA), a opis słowny i próg (C ≥ 0,70) odpowiadają
konwencji 4πA/P². `analiza2/common.py` liczy P²/(4πA) (mediana 1,40 dla cellpose).
Bez rozstrzygnięcia tej niespójności progi kształtu będą nieinterpretowalne.

### 5.4 Kowariaty zakłócające — obowiązkowe
| kolumna | opis | dlaczego |
|---|---|---|
| `centroid_x`, `centroid_y` | pozycja w kadrze [px] | pole oświetlenia nie jest jednorodne |
| `r_norm` | odległość od środka optycznego / półprzekątna kadru | j.w. |
| `bg_frac_in_mask` | udział pikseli maski poniżej progu Otsu | jakość maski |
| `clip_frac` | udział pikseli z dowolnym kanałem ≥ 250 DN | przesterowanie |
| `near_clip_frac` | ≥ 245 DN | margines |
| `touches_border` | bool | kamień ucięty krawędzią kadru |
| `n_contact` | liczba sąsiadujących instancji | przysłonięcie i cień od sąsiada |
| `contact_frac` | udział obwodu stykającego się z inną instancją | j.w. |
| `L_spread_er5` | P95−P5 kanału L\* w wariancie `er5` | amplituda cieniowania 3D |

`area_px` z §5.3 jest jednocześnie najważniejszą kowariatą barwy: na 299 izolowanych
kamieniach z `stones1.png` korelacja L\* z polem wynosi **r = +0,36** (R² = 0,13),
a mediana L\* kamieni z dolnego kwartyla pola to 56,9 wobec 60,2 dla górnego kwartyla —
**różnica 3,3 jednostki L\* przy tym samym materiale**. Sprawdzono, że nie da się tego
usunąć doborem estymatora (mediana / P75 / P90 / mediana jaśniejszej połowy dają
R² od 0,13 do 0,19). Wniosek dla warstwy 3: pole musi wchodzić do analizy progów jako
zmienna towarzysząca albo progi muszą być stratyfikowane po wielkości.

### 5.5 Flagi ważności
`valid_color` (bool) — `n_px_er5 ≥ 50 ∧ ¬touches_border ∧ clip_frac = 0`.
Reguła jest zapisywana w rekordzie `capture` jako łańcuch, żeby dało się ją później
zmienić i przeliczyć wstecz. Kamienie nieważne **pozostają w zbiorze**.

---

## 6. Rekord zdjęcia (`capture`)

Wszystkie pola z §2 (parametry akwizycji + metadane) plus:

| kolumna | opis |
|---|---|
| `image_path`, `image_sha256`, `width`, `height`, `timestamp` | tożsamość pliku |
| `dng_path`, `dng_sha256` | archiwum RAW z §2.4; `null` dopuszczalne tylko poza badaniem progów. Nazwa `dng_*`, a nie `raw_*`, żeby nie kolidowała z wariantem maski `raw` z §4 |
| `tuning_file`, `tuning_file_sha256` | **suma kontrolna, nie sama ścieżka** — plik strojenia bywa aktualizowany razem z pakietem libcamera i podmiana pod tą samą nazwą unieważnia progi bez żadnego widocznego sygnału |
| `isp_sharpness`, `isp_denoise`, `isp_saturation`, `isp_contrast`, `isp_brightness` | wartości faktycznie przekazane do `rpicam-still` (§2.2) |
| `ccm` | `ColourCorrectionMatrix` z metadanych, 9 wartości (§2.3) |
| `rpicam_version`, `libcamera_version` | wersje toru akwizycji |
| `colorspace_transform` | np. `sRGB(D65,2°)→CIELAB, OpenCV 4.14` |
| `mm_per_px`, `scale_source` | skala i sposób jej uzyskania; obecnie w `analiza/an3.py` jest **założenie** 35,9 µm/px (12 mm @ 290 mm), nie pomiar wzorca |
| `otsu_threshold_dn` | próg pierwszego planu (dla `stones1.png` / crop: 112 DN) |
| `foreground_frac` | udział pierwszego planu w kadrze (`stones1.png`: 57,4%) |
| `flatfield_id` | identyfikator użytej korekcji flat-field lub `null` |
| `reference_patch_*` | pomiar wzorca bieli/szarości w kadrze — patrz §6.1 |
| `illum_grid_p98_L` | siatka 8×6 wartości P98 L\* pikseli kamienia w kaflach |
| `illum_range_p98_L` | rozpiętość tej siatki |

Kontrola pola oświetlenia (kafle 8×6, `stones1.png`): P98 L\* od 66,1 do 69,4,
rozpiętość **3,3 jedn.**, centrum 69,0 wobec skrajnych kolumn 67,0. Sama mediana L\*
kafla ma rozpiętość 7,1 jedn., ale jest silnie skorelowana z pokryciem kamieniami
(r = +0,82), czyli miesza spadek oświetlenia z cieniem międzykamiennym w gęstym
usypisku. Dlatego jako miarę pola oświetlenia raportujemy P98, nie medianę.

Te 3,3 jedn. zmierzono **z włączoną korekcją ALSC** z domyślnego pliku strojenia.
Po przejściu na `imx477_scientific.json` (§2.3) ALSC znika i wartość `illum_range_p98_L`
wzrośnie — to jest wskaźnik, na którym weryfikuje się skuteczność własnego flat-fieldu.

### 6.1 Kotwica fotometryczna — wymagana do progów bezwzględnych

W obecnym stanowisku **nie ma w scenie żadnego odniesienia bieli**, więc L\* = 100 nie
odpowiada niczemu fizycznemu, a wartości L\* mierzą ekspozycję, nie jasność materiału.
Progi bezwzględne na L\* są w tym stanie niewyznaczalne — na `stones1.png` mediana L\*
kamieni wynosi 58,9–62,3 przy maksimum 68,9 dla pojedynczego kamienia.

Specyfikacja wymaga umieszczenia w kadrze, w każdym zdjęciu, **wzorca bieli i wzorca
szarości** (płytka ceramiczna lub Spectralon; poza obszarem materiału, w stałym miejscu).
Analiza zwraca dla każdego wzorca: `L_median`, `a_median`, `b_median`, `sd`, `n_px`,
`clip_frac`. Pola mogą być `null`, jeśli wzorca fizycznie nie ma — ale wtedy rekord
niesie flagę `photometric_anchor = none` i wszystkie wyprowadzone z niego progi są
nieważne poza tym jednym stanowiskiem i tą jedną sesją.

Kotwica daje trzy rzeczy naraz: skalę bezwzględną L\*, punkt neutralny do korekty
offsetu a\*/b\* (zmierzony offset materiału: a\* = −4,5, b\* = −4,3 w centrum kadru;
mediana C\*ab = 6,31 — czyli sam odcień białego marmuru „w tym torze" zjada więcej
niż typowy budżet ΔE = 5), oraz detektor dryfu oświetlenia między sesjami.

---

## 7. Rekord próbki (`sample`)

Liczony z rekordów kamieni o `valid_color = true`; liczba odrzuconych raportowana osobno.

| grupa | zawartość |
|---|---|
| liczności | `n_stones`, `n_valid`, `n_invalid` z rozbiciem na przyczynę |
| barwa | dla `L`, `a`, `b`, `C_ab` z wariantu `er5`: `mean`, `median`, `sd`, `MAD`, `min`, `max`, `p01`, `p05`, `p10`, `p25`, `p75`, `p90`, `p95`, `p99` |
| kształt | to samo dla `circularity_4piA_P2`, `aspect_ratio`, `solidity`, `equiv_diameter_px`, `area_px` |
| granulometria | `area_px` percentyle + `d10`, `d50`, `d90` w mm, jeśli `mm_per_px` pochodzi z pomiaru wzorca |
| kowariaty próbki | `foreground_frac`, mediana `n_contact`, mediana `contact_frac`, `illum_range_p98_L` |
| kontrola biasu | `corr_L_area` — współczynnik korelacji L\* z polem **w tej próbce**; wartość odstająca od typowej oznacza zmianę ułożenia lub oświetlenia, nie materiału |

Pełne percentyle zamiast średniej i mediany są konieczne, bo progi na poziomie próbki
najprawdopodobniej trzeba będzie oprzeć na ogonie rozkładu, a nie na jego środku,
i w chwili zbierania danych nie wiadomo, na którym.

---

## 8. Protokół zbierania danych do kalibracji progów

Kolejność jest wiążąca — każdy etap ustala wielkość, bez której następny nie ma sensu.

**0. Zamrożenie toru akwizycji.** Wykonanie §2 w całości: docelowy plik strojenia,
ponowny dobór `--shutter`, `--sharpness 0`, `--denoise off`, jawne 1.0/1.0/0,
flat-field, wzorzec bieli w kadrze, archiwum DNG. Dopiero po tym etapie zebrane dane
mają wartość trwałą. Każdy z etapów A–F wykonany przed zamknięciem etapu 0 trzeba
będzie powtórzyć — dotyczy to również pomiarów już wykonanych na `stones1.png`,
które mają status danych orientacyjnych, nie kalibracyjnych.

**A. Powtarzalność ujęcia.** Jedno ułożenie materiału, ≥10 kolejnych zdjęć bez dotykania.
Daje σ_frame — czysty szum toru (sensor, ISP, segmentacja). Zmierzony dolny kres:
dwie losowe połówki pikseli tego samego kamienia dają medianę ΔE00 = 0,21 (P95 = 0,78),
więc szum samego pomiaru barwy jest pomijalny; σ_frame zmierzy dodatkowo powtarzalność
masek, która jest realnym niewiadomym.

**B. Powtarzalność ułożenia.** Ten sam materiał, ≥10 ponownych wysypań, po jednym
zdjęciu. Daje σ_layout. **To jest właściwy dolny kres każdego progu na poziomie próbki** —
żaden próg nie może rozróżniać różnic mniejszych niż σ_layout, bo one powstają z samego
przesypania tego samego materiału.

**C. Stabilność w czasie.** Ten sam materiał referencyjny, ≥10 sesji w różnych dniach,
z zapisem `Lux`, czasu od włączenia oświetlacza i temperatury. Daje dryf stanowiska
i odpowiedź na pytanie, jak często odnawiać wzorzec.

**D. Zmienność materiału akceptowanego.** ≥20 różnych próbek/dostaw uznanych przez
odbiorcę za dobre. Daje rozkład wewnątrzklasowy — z niego bierze się kandydatów na progi.

**E. Materiał odrzucany i graniczny.** ≥10 próbek z etykietą eksperta i podaną przyczyną
odrzucenia (za ciemny / kremowy / zażółcony / za mało okrągły…). **Bez tego zbioru progów
nie da się wyznaczyć — można tylko opisać, co jest typowe.** To jest najczęściej
pomijany i najtrudniejszy do zdobycia element całego badania; warto go planować od razu.

**F. Wzorce fizyczne.** Karta barw (np. ColorChecker) sfotografowana w tej samej scenie,
raz na sesję. Umożliwia przeliczenie skali przyrządowej na kolorymetryczną i przeniesienie
progów na drugie stanowisko.

Punkt odniesienia z już zebranych danych — pojedyncze zdjęcie `stones1.png`, jeden
materiał, wzorzec = mediana tej samej partii: ΔE00 mediana 2,06 / P95 6,36 (321 kamieni
w gęstym kadrze) oraz 2,65 / 6,03 (299 izolowanych). Rozrzut wewnątrz jednorodnego
materiału na jednym zdjęciu sięga więc ΔE00 ≈ 6, i to jest liczba, którą etapy A–C mają
rozłożyć na składowe.

---

## 9. Procedura wyznaczania progów (warstwa 3, opis wymagań)

Specyfikacja nie przesądza progów, ale przesądza, co musi być spełnione, żeby próg dało
się uznać za wyznaczony:

1. **Jednostka decyzji rozstrzygnięta jawnie.** Dane wskazują, że barwa pojedynczego
   kamienia jest silnie obciążona geometrią (R² ≈ 0,13–0,19 względem samego pola),
   podczas gdy agregat próbki to uśrednia. Domyślnie: decyzja na poziomie próbki,
   wartości pojedynczych kamieni jako materiał diagnostyczny. Odwrotny wybór wymaga
   wykazania, że separacja przekracza σ_layout z etapu B.
2. **Wzorzec zdefiniowany, zamrożony i wersjonowany** — jako mediana wskazanej,
   wymienionej z nazwy puli próbek OK, z zapisanym `reference_id`. Uwaga na skalę
   problemu: na tym samym zdjęciu wzorzec policzony z centrum kadru różni się od wzorca
   policzonego z kamieni izolowanych o **ΔE00 = 4,25**. Pula, z której liczony jest
   wzorzec, jest częścią definicji progu.
3. **Margines separacji > szum.** Różnica median między klasą OK a NOK musi przekraczać
   σ_layout (etap B) z zapasem; próg mieszczący się w szumie jest odrzucany niezależnie
   od tego, jak dobrze wypada na danych treningowych.
4. **Raportowana skuteczność z przedziałami ufności** (FPR/FNR na zbiorze z etapu E),
   plus walidacja na próbkach odłożonych.
5. **Kontrola redundancji.** Kryterium `ColorOK% ≥ X` zdefiniowane przez `ΔE00 ≤ ΔEmax`
   implikuje `P95(ΔE00) ≤ ΔEmax` przy X = 95%. Kryteria na poziomie próbki muszą być
   sprawdzone pod kątem takiej implikacji, żeby nie tworzyć warunków, które nigdy
   nie odrzucą niczego samodzielnie.
6. **Kierunkowość.** ΔE jest symetryczne — kamień jaśniejszy od wzorca daje takie samo
   ΔE jak ciemniejszy. Jeśli odchylenie ma być karane tylko w jedną stronę, potrzebny
   jest osobny warunek jednostronny (np. na samym L\*), i to musi być zapisane wprost
   jako intencja, a nie wynikać przypadkowo z doboru dwóch progów.

---

## 10. Format wyjścia

Na jedno zdjęcie:

```
<capture_id>/
  capture.png           # obraz po ISP, wejście warstwy pomiarowej
  capture.dng           # archiwum RAW z §2.4 — nietykalne, nie wchodzi do pomiaru
  meta.json             # surowe metadane rpicam-still
  stones.parquet        # rekordy z §5, jeden wiersz na kamień
  capture.json          # rekord z §6
  sample.json           # rekord z §7 (agregat; przeliczalny z stones.parquet)
  labels.npy            # mapa instancji, 0 = tło, 1..N — do odtworzenia pomiaru
  masks_meta.json       # model, parametry, wersje bibliotek
  overlay.png           # kontrola wzrokowa
```

Zbiór do badania progów: konkatenacja `stones.parquet` i `sample.json` po wszystkich
`capture_id`, złączona po kluczach z §3.

**Determinizm.** Ten sam plik wejściowy i ta sama `pipeline_version` muszą dawać
bitowo identyczne `stones.parquet`. Ziarna generatorów losowych zapisywane w
`masks_meta.json`.

---

## 11. Kryteria odbioru samej warstwy pomiarowej

Do spełnienia zanim ruszy zbieranie danych do progów:

| kryterium | sposób sprawdzenia |
|---|---|
| determinizm | dwukrotne uruchomienie na tym samym pliku → identyczne sumy kontrolne wyjścia |
| powtarzalność na serii ujęć | etap A z §8; raportowane σ_frame w ΔE00 i w L\* |
| wrażliwość na definicję pikseli | różnice `raw` / `er3` / `er5` zmierzone i udokumentowane (obecnie mediana L\* 61,8 / 62,3 / 62,8) |
| kompletność kowariat | każdy rekord kamienia ma wypełnione wszystkie pola z §5.4 |
| kontrola wzrokowa masek | `overlay.png` dla losowej próby, ocena człowieka |
| zgodność jednostek | obie definicje kolistości policzone i wzajemnie zgodne (`C_4piA_P2 × C_P2_4piA = 1`) |
| płaskość pola oświetlenia | zdjęcie jednorodnej białej powierzchni przy docelowym pliku strojenia; `illum_range_p98_L` po korekcji flat-field na poziomie nie gorszym niż obecne 3,3 jedn. |
| skutek wyłączenia denoise | test połówkowy ΔE00 powtórzony po zmianie `--denoise` na `off`; kryterium: mediana < 1,0 (§2.2) |
| skutek wyłączenia wyostrzania | para A/B tej samej sceny przy `--sharpness 0` i `1.0`, udokumentowana różnica profilu krawędzi (§2.2) |

---

## 12. Czego ten dokument świadomie nie rozstrzyga

- wartości progów — to przedmiot badania z §8–9;
- czy decyzja ma zapadać na poziomie kamienia czy próbki — do rozstrzygnięcia danymi;
- postać korekcji flat-field — **sam fakt, że jest wymagana, jest już rozstrzygnięty**
  (§2.3: plik scientific nie zawiera ALSC). Otwarte zostaje, jak ją wyznaczyć.
  Sprawdzono, że dopasowanie wielomianu 2. stopnia po kadrze do wartości pojedynczych
  kamieni nie poprawia ΔE00 P95 (6,03 → 6,13), bo dominującą składową rozrzutu jest
  cieniowanie 3D pojedynczego kamienia, a nie gradient kadru; flat-field musi więc
  pochodzić ze zdjęcia jednorodnego tła, nie z regresji po kamieniach;
- wybór modelu segmentacji — `analiza2/wnioski.md` wskazuje cellpose cyto3 `cellprob=-1`
  jako podstawę pre-anotacji; warstwa pomiarowa jest wobec źródła masek neutralna, wymaga
  jedynie ich zapisania i zwersjonowania.
