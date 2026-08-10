# Przygotowanie i rozsypanie materiału — instrukcja stanowiskowa

Procedura przygotowania próbki do zdjęcia. Celem jest **losowa, jednowarstwowa,
rzadka warstwa**, w której kamyki się nie stykają — bo dopiero wtedy mierzony obrys
jest obrysem kamienia, a nie wycinkiem wyciętym przez sąsiadów
(`spec-analizy-ksztaltu.md` §2.1).

Rozsypywanie jest **operacją pomiarową, nie czynnością pomocniczą**. Jej parametry
(dawka, wysokość, liczba stuknięć) są zamrażane i zapisywane tak samo jak czas
naświetlania. Jeżeli procedura nie jest powtarzalna, to σ_layout z etapu B protokołu
mierzy zmienność sposobu sypania, a nie zmienności materiału — i cała kalibracja progów
opiera się na złej liczbie.

---

## 0. Najpierw kalibracja skali

**Wszystkie liczby w tym dokumencie skalują się z wielkością ziarna, a wielkość ziarna
nie jest jeszcze zmierzona.** `analiza/an3.py` przyjmuje 35,9 µm/px jako **założenie**
(obiektyw 12 mm, odległość 290 mm), nie jako pomiar wzorca. Przy tym założeniu:

| wielkość | wartość |
|---|---|
| kadr | 145,6 × 109,1 mm = 15 891 mm² = 1,59 dm² |
| mediana średnicy ekwiwalentnej | 1,44 mm |
| P99 średnicy ekwiwalentnej | 1,90 mm |
| P99 dłuższej osi (wymiar decydujący o oczku sitka) | **2,39 mm** |
| średnie pole rzutu ziarna | 1,62 mm² |

Jeśli rzeczywista skala okaże się inna, dawka zmienia się **liniowo** z wielkością ziarna,
a oczko sitka **proporcjonalnie**. Sfotografowanie wzorca wymiaru (linijka warsztatowa,
szachownica) i wpisanie zmierzonego `mm_per_px` jest warunkiem, żeby poniższe liczby
miały sens — a nie osobnym zadaniem na później.

---

## 1. Dobór dawki

### 1.1 Wzór

```
m = 0,51 · c · A · ρ · d
```

| symbol | znaczenie | wartość dla tego stanowiska |
|---|---|---|
| `m` | masa dawki [g] | — |
| `c` | docelowe pokrycie kadru | **0,10** (patrz 1.2) |
| `A` | pole kadru [mm²] | 15 891 |
| `ρ` | gęstość materiału [g/mm³] | 0,0027 (marmur) |
| `d` | mediana średnicy ekwiwalentnej [mm] | 1,44 |

Stała 0,51 wynika z przyjętego współczynnika kształtu ziarna kruszonego
(objętość ≈ 0,4·d³). Jest to oszacowanie — dawkę i tak ustala się doświadczalnie (1.3),
a wzór służy do trafienia w rząd wielkości i do przeliczenia po zmianie frakcji.

### 1.2 Tablica dawek

| pokrycie | kamieni w kadrze | dawka | gęstość powierzchniowa | kamieni ze swobodnym obrysem |
|---|---|---|---|---|
| 8 % | ~785 | **2,5 g** | 1,6 g/dm² | ~770 |
| **10 %** | **~980** | **3,1 g** | **2,0 g/dm²** | **~960** |
| 12 % | ~1180 | 3,8 g | 2,4 g/dm² | ~1150 |
| 15 % | ~1470 | 4,7 g | 3,0 g/dm² | ~1440 |
| 20 % | ~1960 | 6,3 g | 4,0 g/dm² | ~1670 |

Ostatnia kolumna z pomiaru zależności udziału kamieni swobodnych od lokalnego pokrycia
(`spec-analizy-ksztaltu.md` §2.1): poniżej 15 % pokrycia swobodnych jest ~98 %, w przedziale
15–30 % już tylko ~71 %.

**Wartość zalecana: `c` = 10 %, tolerancja 8–13 %.** Powyżej 15 % udział swobodnych zaczyna
gwałtownie spadać, a poniżej 8 % rośnie liczba zdjęć potrzebnych na tę samą liczbę pomiarów.
Przy 10 % jedno zdjęcie daje ~960 kamieni z pełnym obrysem — wielokrotnie więcej, niż
potrzeba do wyznaczenia percentyli rozkładu.

Dla porównania: obecne zdjęcia `stones1/2.png` mają pokrycie **62,5 %** i dają 182 kamienie
ze swobodnym obrysem z 7969. Rzadkie wysypanie daje **pięciokrotnie więcej użytecznych
pomiarów przy czterokrotnie mniejszej liczbie ziaren w kadrze**.

### 1.3 Kalibracja dawki na stanowisku

Wzoru nie traktujemy jako ostatecznego. Procedura ustalenia dawki:

1. Odważyć 3,1 g, rozsypać wg §4, zrobić zdjęcie.
2. Uruchomić `analiza3/measure.py` i odczytać `foreground_frac` z `capture.json`.
3. Skorygować dawkę proporcjonalnie: `m_nowa = m · c_docelowe / foreground_frac`.
4. Powtórzyć, aż `foreground_frac` mieści się w 8–13 % w trzech kolejnych próbach.
5. Zapisać ustaloną dawkę w profilu akwizycji jako parametr, nie w notatniku.

Dawkę ustala się **osobno dla każdej frakcji materiału**, bo wzór jest liniowy w `d`.

---

## 2. Sitko

Sitko pełni tu funkcję **dyspergatora, nie klasyfikatora**. Musi przepuścić cały materiał
bez zatrzymania choćby najgrubszych ziaren — zatrzymanie oznaczałoby, że próbka trafiająca
na płytę jest przesiana, czyli systematycznie pozbawiona grubego ogona rozkładu. To byłby
błąd wprost w wielkości, którą granulometria ma mierzyć.

| parametr | wartość | uzasadnienie |
|---|---|---|
| **oczko** | **8 mm** (kwadratowe) | reguła: ≥ 4 × największy wymiar ziarna. P99 dłuższej osi = 2,39 mm → 8 mm daje ponad trzykrotny zapas i zerowe zatrzymanie |
| **materiał siatki** | **stal nierdzewna** | stal zwykła rdzewieje, a rdza na białym marmurze wygląda jak zanieczyszczenie materiału i zostanie zmierzona jako takie |
| **rama** | stal nierdzewna lub aluminium anodowane, **nie plastik** | plastik elektryzuje się i zatrzymuje pył |
| **wymiar wewnętrzny ramy** | **≥ 190 × 150 mm** (lub okrągła Ø 200 mm) | większy niż kadr 145,6 × 109,1 mm z zapasem ≥ 20 mm z każdej strony — patrz niżej |
| **wysokość ramy** | 40–50 mm | dawka nie wysypuje się bokiem podczas stukania |
| **wysokość nad płytą** | **100 mm**, ustalona mechanicznie | patrz §2.1 |
| **mocowanie** | prowadnice / jarzmo, **nie w ręku** | wysokość i pozycja muszą być powtarzalne; trzymanie na oko wprowadza zmienność procedury do σ_layout |

**Sitko szersze niż kadr** to najtańsza poprawa jednorodności: przepływ przez sitko jest
zawsze gęstszy w środku i rzadszy przy ramie. Jeśli sitko i płyta są większe od pola
widzenia, ten gradient wypada poza kadr i fotografowany jest wyłącznie obszar
o wyrównanej gęstości.

### 2.1 Wysokość zrzutu

Kompromis między dwoma zjawiskami:

- **za nisko** → ziarna lądują pionowo pod oczkami i na zdjęciu odwzorowuje się **siatka
  sitka**; przy oczku 8 mm i dawce 10 % przypada tylko ~4 ziarna na oczko, więc ryzyko
  jest realne;
- **za wysoko** → ziarno uderza z prędkością √(2gh) i odbija się, a potem toczy, tworząc
  skupiska i wypadając poza obszar pomiarowy.

Wartość startowa **100 mm** (prędkość uderzenia ~1,4 m/s). Wysokość jest parametrem
profilu i podlega weryfikacji testem z §6.2. Jeżeli test wykaże odwzorowanie siatki:
najpierw zwiększyć wysokość do 150 mm, dopiero potem rozważać drobniejsze oczko.

### 2.2 Czego sitko nie robi

Oczko 8 mm **nie rozbija zlepków** złożonych z kilku ziaren — takie zlepki mają 3–5 mm
i przechodzą swobodnie. Jedynym zabezpieczeniem przed zlepkami jest suchość materiału
(§3.1). Sitko rozbija wyłącznie większe grudy i metrykuje przepływ.

---

## 3. Przygotowanie materiału

### 3.1 Suszenie

Materiał musi być **suchy**. Wilgoć powoduje zlepianie się ziaren, którego sitko nie
usuwa, a zlepek zostanie zmierzony jako jeden duży, nieregularny kamień — czyli trafi
w metryki kształtu i granulometrii naraz.

Jeśli materiał przyszedł wilgotny lub był magazynowany na zewnątrz: suszyć w 105 °C do
stałej masy (dwa ważenia w odstępie godziny różniące się o mniej niż 0,1 %), następnie
studzić do temperatury pomieszczenia w zamkniętym pojemniku. Fotografowanie ciepłego
materiału jest błędem — ciepłe powietrze nad płytą powoduje drgania optyczne przy 65 ms
ekspozycji.

### 3.2 Pomniejszanie próbki

Dawka to ~3 g z dostawy liczonej w kilogramach. To jest stosunek rzędu 1:10 000 i
**najpoważniejsze zagrożenie dla reprezentatywności całego badania** — materiał sypki
segreguje się w transporcie, drobne frakcje wędrują na dół pojemnika. Zgarnięcie łyżki
z wierzchu worka daje próbkę systematycznie zgrubioną.

Pomniejszanie kaskadowe, zgodnie z zasadami redukcji próbek kruszyw (EN 932-2):

1. **25 kg → ~1 kg**: dzielnik szczelinowy (riffle) albo stożkowanie i ćwiartowanie,
   powtórzone tyle razy, ile trzeba.
2. **1 kg → ~50 g**: dzielnik szczelinowy o mniejszej szczelinie.
3. **50 g → 3 g**: rozsypać 50 g cienką warstwą na tacy, pobrać **co najmniej 8 przyrostów**
   szpatułką z losowo rozmieszczonych miejsc, aż do uzyskania dawki. Riflowanie poniżej
   ~20 g przestaje być wiarygodne.

Podpróbka 50 g wystarcza na kilkanaście dawek, czyli na komplet ujęć jednej próbki —
i wszystkie pochodzą wtedy z tego samego, jednorodnie pomniejszonego materiału.

### 3.3 Pył i drobna frakcja

Pył poniżej ~0,1 mm przykleja się do ziaren i do tła, zaburza próg Otsu i tworzy fałszywe
małe obiekty. Kusi, żeby go odsiać — ale **odsianie pyłu zmienia rozkład uziarnienia**,
czyli wielkość, którą badanie ma mierzyć.

Rozstrzygnięcie: usuwanie pyłu jest **parametrem procedury**, nie decyzją operatora na
miejscu. Jeśli się je stosuje, to zawsze, tym samym sitkiem, a **masa frakcji usuniętej
jest ważona i zapisywana** dla każdej próbki. Jeśli specyfikacja zakupowa materiału
obejmuje zawartość pyłu, usuwać go nie wolno.

---

## 4. Procedura rozsypania

Krok po kroku. Liczby w nawiasach to parametry profilu — muszą być identyczne przy każdym
powtórzeniu.

1. **Sprawdzić płytę.** Czysta, sucha, bez pojedynczych ziaren z poprzedniego ujęcia.
   Wzorce bieli i szarości na swoich miejscach.
2. **Odważyć dawkę** (3,1 g ±0,05 g) na wadze o rozdzielczości 0,01 g. Ważyć każdą dawkę,
   nie odmierzać objętościowo.
3. **Wsypać dawkę do sitka**, rozprowadzając ją po całej powierzchni siatki, a nie na
   środek. Kupka na środku przejdzie przez kilka oczek i wyląduje skupiskiem.
4. **Osadzić sitko w jarzmie** na ustalonej wysokości (100 mm).
5. **Stuknąć w ramę sitka** ustaloną liczbę razy (**10 stuknięć**) drewnianym trzonkiem,
   w stałym miejscu ramy, w równym tempie ok. 2 stuknięć na sekundę. Nie potrząsać,
   nie kręcić — stukanie jest powtarzalne, potrząsanie nie.
6. **Zdjąć sitko pionowo w górę.** Ruch boczny przy zdejmowaniu zrzuca pozostałe ziarna
   nierównomiernie.
7. **Sprawdzić wzrokowo**: brak zlepków, brak ziaren na obrzeżu poza obszarem pomiarowym,
   brak pustego pasa po zdjęciu sitka.
8. **Odczekać** (**2 s**) i wykonać zdjęcie.
9. **Zważyć resztę w sitku.** Powinna być zerowa w granicach rozdzielczości wagi.
   Jakiekolwiek zatrzymanie oznacza, że oczko jest za małe i próbka na płycie jest
   przesiana — ujęcie do odrzucenia, sitko do wymiany.

### 4.1 Płyta pomiarowa

| parametr | wymaganie |
|---|---|
| powierzchnia | matowa, ciemna, twarda, płaska; **nie szkło i nie polerowany metal** — odbicia i odbijanie się ziaren |
| pole płaskie | ≥ kadr + 20 mm z każdej strony |
| **rant** | **≥ 5 mm wysokości, poza kadrem** |
| wzorce barwne | stałe gniazdo poza obszarem materiału, w kadrze |
| czyszczenie | przed każdym ujęciem, pędzlem antystatycznym |

Rant jest wymaganiem, nie wygodą: bez niego ziarna staczają się z płyty, a **staczają się
preferencyjnie te najbardziej okrągłe**. Efektem jest rozkład kształtu przesunięty w stronę
ziaren kanciastych — czyli błąd systematyczny dokładnie w mierzonej wielkości.

---

## 5. Powtórne układanie i ubytek materiału

Etap B protokołu (powtarzalność ułożenia) wymaga wielokrotnego rozsypania **tego samego
materiału** — inaczej mierzy się różnicę między dawkami, a nie między ułożeniami.

- Materiał zbierać z płyty pędzlem do naczynka, **nie zsypywać przez krawędź** (traci się
  wtedy to, co przy rancie).
- **Maksymalnie 10 powtórnych ułożeń tej samej dawki.** Marmur ściera się przy każdym
  przesypaniu, a ścieranie generuje pył i zaokrągla naroża — po kilkunastu cyklach mierzy
  się skutek obsługi, nie materiał.
- **Ważyć dawkę po każdym zebraniu.** Ubytek powyżej 2 % masy początkowej oznacza koniec
  serii: albo materiał się kruszy, albo część zostaje na płycie i w naczynku.
- Do etapów D i E (różne próbki) używać **świeżej dawki na każde ułożenie** — materiału
  jest dużo, a świeża dawka eliminuje problem ścierania.

---

## 6. Kryteria akceptacji rozsypania

Liczone przez `analiza3/measure.py` z gotowego zdjęcia. Rozsypanie nieudane jest tanie do
powtórzenia; nieudane, ale niewykryte, zanieczyszcza zbiór.

### 6.1 Progi liczbowe

| miara | źródło | kryterium |
|---|---|---|
| `foreground_frac` | `capture.json` | 8–13 % |
| udział kamieni `contact_frac ≤ 0,2` | `stones.parquet` | **≥ 85 %** |
| liczba instancji | `sample.json` | w granicach ±25 % wartości oczekiwanej z tablicy 1.2 |
| mediana `equiv_diameter_px` | `sample.json` | w granicach ±10 % wartości z poprzednich ujęć tej samej próbki — większe odchylenie sugeruje zlepki albo przesianie |
| udział `touches_border` | `stones.parquet` | ≤ 10 % |
| pozostałość w sitku | waga | 0 g |

### 6.2 Test odwzorowania siatki sitka

Wykonywany **raz przy ustalaniu profilu** i po każdej zmianie sitka lub wysokości zrzutu,
nie przy każdym ujęciu.

Z kolumn `centroid_x`, `centroid_y` w `stones.parquet` policzyć rozkład odległości do
najbliższego sąsiada. Przy pokryciu 10 % gęstość wynosi ~0,062 ziarna/mm², więc średnia
odległość do najbliższego sąsiada powinna wyjść rzędu **2 mm (~56 px)**.

Sygnały ostrzegawcze:

- **wyraźny nadmiar par w odległości bliskiej podziałce siatki (8 mm ≈ 223 px)** →
  odwzorowanie sitka; zwiększyć wysokość zrzutu;
- **nadmiar par w odległościach bardzo małych** → zlepki albo odbijanie się i toczenie;
  sprawdzić suchość materiału i powierzchnię płyty;
- **rozkład znacznie węższy niż dla rozmieszczenia losowego** → ziarna układają się
  regularnie, czyli rozsypanie nie jest losowaniem i kolejne ułożenia nie są niezależne.

Porównanie z idealnym procesem losowym jest przybliżone, bo ziarna mają skończony rozmiar
i nie mogą się nakładać. Praktyczniejsze kryterium: **rozkład ma być powtarzalny między
ułożeniami i pozbawiony piku przy podziałce siatki.**

---

## 7. Co trafia do rekordu ujęcia

Parametry procedury są częścią profilu akwizycji (`spec-akwizycji.md` §3) i muszą być
zapisane przy każdym ujęciu:

```
dose_g               masa dawki [g], ważona
sieve_id             identyfikator sitka
sieve_aperture_mm    oczko [mm]
drop_height_mm       wysokość zrzutu [mm]
taps                 liczba stuknięć
settle_s             czas do wyzwolenia migawki [s]
plate_id             identyfikator płyty
material_dried       czy suszony, temperatura i czas
fines_removed_g      masa odsianego pyłu, jeśli procedura go przewiduje
subsample_id         identyfikator podpróbki, z której pochodzi dawka
layout_reuse_n       który raz z rzędu ta sama dawka jest układana
sieve_residue_g      pozostałość w sitku po rozsypaniu
```

Bez `subsample_id` i `layout_reuse_n` nie da się później odróżnić zmienności materiału od
zmienności ułożenia i od ścierania — czyli rozłożyć wariancji na składowe, o co w etapach
A–C protokołu chodzi.

---

## 8. Dlaczego nie wibrator pod płytą

Rozważany był mały silniczek wibracyjny (10 × 2,7 mm, 3 V, 11 000 obr/min) pod płytą,
uruchamiany na kilka sekund. Odrzucone z trzech powodów:

1. **Figury Chladniego.** Punktowe wymuszenie ~183 Hz na sztywnej płycie zbiera lekkie
   ziarna na liniach węzłowych. Zamiast równomiernego rozkładu powstają powtarzalne
   prążki, a kolejne ułożenia przestają być niezależnymi losowaniami — czyli σ_layout
   z etapu B traci sens.
2. **Segregacja rozmiarowa.** Kilka sekund wibracji granulatu sortuje ziarna po wielkości
   (efekt orzecha brazylijskiego). To jest błąd systematyczny wpisany w granulometrię.
3. **Sprzężenie z kamerą.** Ciągła wibracja podawana w konstrukcję stanowiska rozluźnia
   z czasem zablokowaną ostrość, na której stoi cała powtarzalność.

Do tego wibrator rozwiązuje niewłaściwy problem: rozprowadza materiał już leżący na płycie,
podczas gdy właściwym zadaniem jest **kontrolowane nasypanie**. Sitko rozwiązuje zadanie
u źródła i nie ma żadnej z trzech powyższych wad.

Wibrator pozostaje sensowny w jednej roli: jako **podajnik pod lejkiem** przy dozowaniu
materiału, gdzie nie dotyka płyty pomiarowej ani kolumny kamery.

---

## 9. Do ustalenia doświadczalnie

Wartości podane wyżej jako startowe, wymagające potwierdzenia na stanowisku:

- **wysokość zrzutu** (start 100 mm) — testem z §6.2;
- **liczba stuknięć** (start 10) — dobrać tak, żeby cała dawka przeszła, bez nadmiaru;
- **czas do wyzwolenia migawki** (start 2 s) — sprawdzić, czy ziarna nie toczą się jeszcze
  po płycie; metryką jest `focus_metric` ze `spec-akwizycji.md` §6 przy rosnącym opóźnieniu;
- **dawka** — procedurą z §1.3;
- **oczko sitka** — potwierdzić zerową pozostałość dla najgrubszej frakcji, jaka wchodzi
  w zakres badania, a nie tylko dla tej jednej próbki.
