# Specyfikacja funkcjonalna programu akwizycji

Program obsługuje stanowisko fotograficzne przy zbieraniu materiału do wyznaczenia
progów jakości. Jego zadaniem jest wyprodukować archiwum zdjęć, które **da się
później połączyć w jeden zbiór** i przepuścić przez `analiza3/measure.py`.

Dokument opisuje warstwę 1 z podziału w `spec-analizy-barwy.md` §1. Warstwa 2 (pomiar)
jest już zaimplementowana w `analiza3/`; warstwy 3 (kalibracja progów) i 4 (decyzja)
są przedmiotem badania.

## 0. Zasada nadrzędna

> Program ma **uniemożliwić** zebranie danych, których później nie da się porównać.

To jest jedyne kryterium, według którego należy rozstrzygać wątpliwości projektowe.
Zdjęcie zapisane z niezweryfikowanymi parametrami jest gorsze niż brak zdjęcia, bo
zanieczyszcza zbiór i wychodzi na jaw dopiero przy analizie, gdy materiał już nie
istnieje w tej postaci. Stąd trzy reguły, z których wynika reszta specyfikacji:

1. **Kontrakt akwizycji jest sprawdzany po każdym ujęciu, a nie raz na sesję.**
   Ujęcie niezgodne z profilem nie trafia do archiwum jako ważne.
2. **Tożsamość próbki i werdykt eksperta deklaruje się przed ujęciem, nie po.**
   Etykieta dopisywana z pamięci po dwóch godzinach jest niewiarygodna, a bez etykiet
   materiału odrzuconego progów nie da się wyznaczyć w ogóle (`spec-analizy-barwy.md` §8 E).
3. **Archiwum jest niezmienne.** Program nigdy nie nadpisuje, nie przekodowuje i nie
   kasuje zapisanych plików. Ujęcia odrzucone są przenoszone, nie usuwane.

## 1. Zakres

**Program robi:**
- wymusza i weryfikuje stałe parametry akwizycji,
- prowadzi operatora przez sesję zgodnie z protokołem badawczym,
- zbiera metadane, których kamera nie zna (tożsamość partii, werdykt eksperta),
- wykonuje szybką kontrolę jakości ujęcia na miejscu,
- zapisuje archiwum w układzie gotowym do analizy, z sumami kontrolnymi.

**Program nie robi:**
- nie segmentuje, nie liczy L\*a\*b\*, nie liczy ΔE, nie wystawia ocen — to warstwy 2–4,
- nie koryguje obrazu (flat-field, balans bieli, gamma) — korekcje są operacją analizy,
  wykonywaną na niezmienionym archiwum,
- nie kasuje ani nie „poprawia" ujęć nieudanych.

## 2. Model danych i identyfikatory

Hierarchia z `spec-analizy-barwy.md` §3, uzupełniona o **sesję** — jeden ciągły okres
pracy stanowiska bez wyłączania oświetlenia:

```
study  →  batch (dostawa)  →  sample (jedna porcja materiału)
                                 └─ layout (jedno wysypanie)
                                      └─ frame (jedno ujęcie)
session ⟂ (przecina hierarchię: każdy capture należy do dokładnie jednej sesji)
```

| klucz | typ | kto nadaje | uwagi |
|---|---|---|---|
| `study_id` | str | konfiguracja | jedno badanie = jeden zamrożony profil akwizycji |
| `batch_id` | str | operator | dostawa/partia od dostawcy |
| `sample_id` | str | operator | porcja materiału; wielokrotnie fotografowana |
| `layout_seq` | int | **program** | inkrementowany, gdy operator zadeklaruje przesypanie |
| `frame_seq` | int | **program** | inkrementowany przy powtórzeniu ujęcia bez dotykania |
| `session_id` | str | program | `YYYYMMDD-HHMM` startu sesji |
| `capture_id` | str | program | `{study}_{batch}_{sample}_L{layout:02d}F{frame:02d}_{YYYYmmdd-HHMMSS}` |

`layout_seq` i `frame_seq` **muszą** być nadawane przez program, a nie wpisywane ręcznie.
Cały protokół z §8 specyfikacji analizy (rozkład wariancji na σ_frame, σ_layout i dryf
czasowy) stoi na tym, że te dwa liczniki znaczą dokładnie to, co znaczą. Operator ma
w interfejsie dwa różne przyciski — „kolejne ujęcie" i „przesypano materiał" — i to jest
najważniejsza decyzja ergonomiczna w całym programie.

## 3. Profil akwizycji

Profil to zamrożony zestaw parametrów toru. Jest plikiem, ma identyfikator i sumę
kontrolną, i **jest częścią tożsamości każdego zdjęcia**.

```jsonc
{
  "profile_id": "P1-scientific-2026xxxx",
  "camera": "imx477 / RPi HQ",
  "resolution": [4056, 3040],
  "shutter_us": 65000,            // do ponownego dobrania po zmianie strojenia
  "analogue_gain": 1.0,
  "awb_gains": [2.36, 2.19],
  "tuning_file": "/usr/share/libcamera/ipa/rpi/vc4/imx477_scientific.json",
  "tuning_file_sha256": "…",
  "isp": { "sharpness": 0, "denoise": "off",
           "saturation": 1.0, "contrast": 1.0, "brightness": 0 },
  "encoding": "png", "raw": true, "immediate": true,
  "optics": { "aperture": "f/4", "focus": "zablokowana", "distance_mm": 290 },
  "reference_patches": [
    { "name": "white", "roi": [3530, 2514, 412, 412] },
    { "name": "grey",  "roi": [3526, 2011, 417, 416] }
  ],
  "calibration": { "flatfield_id": null, "scale_id": null, "colorchart_id": null },
  "expected": { "white_patch_L": null, "max_dn": null, "focus_metric": null }
}
```

Reguły:

- **Profil jest niezmienny w obrębie `study_id`.** Każda zmiana wartości tworzy nowy
  `profile_id`; program odmawia dopisania ujęcia do istniejącego badania pod zmienionym
  profilem i wymaga jawnej decyzji: nowe badanie albo świadome rozgałęzienie z adnotacją.
- `tuning_file_sha256` liczony przy starcie każdej sesji, nie przepisywany z konfiguracji.
  Plik strojenia bywa podmieniany pod tą samą nazwą przy aktualizacji pakietu libcamera
  i jest to zmiana, która unieważnia progi bez żadnego widocznego sygnału.
- Pola `expected.*` wypełnia procedura z §7 (ujęcie odniesienia). Dopóki są `null`,
  program działa, ale kontrola dryfu (§6) jest wyłączona i zapisuje to w rekordzie.

## 4. Przebieg sesji

```
START SESJI
  ├─ odczyt profilu, weryfikacja sha256 pliku strojenia
  ├─ sprawdzenie miejsca na dysku (§11)
  ├─ ujęcie kontrolne (nie trafia do zbioru pomiarowego):
  │    wzorce widoczne? histogram w zakresie? ostrość zgodna z odniesieniem?
  ├─ zapis warunków: czas od włączenia oświetlacza, temperatura, operator
  └─ jeśli profil nie ma ważnej kalibracji flat-field → ostrzeżenie i zapis flagi

PĘTLA PRÓBEK
  ├─ deklaracja próbki: batch_id, sample_id, werdykt eksperta, etap protokołu
  ├─ pozycjonowanie materiału (podgląd na żywo, bez zapisu do archiwum)
  └─ PĘTLA UJĘĆ
       ├─ [kolejne ujęcie]      → frame_seq += 1
       ├─ [przesypano materiał] → layout_seq += 1, frame_seq = 1
       ├─ wykonanie zdjęcia
       ├─ weryfikacja kontraktu (§5) + QC (§6)
       └─ zapis do archiwum albo do kwarantanny, z podaniem przyczyny

KONIEC SESJI
  ├─ podsumowanie: ile ujęć, ile odrzuconych i dlaczego
  ├─ raport dryfu w obrębie sesji (L* wzorca bieli w czasie)
  └─ domknięcie manifestu i dziennika
```

Podgląd do pozycjonowania musi działać **na parametrach profilu**, nie na automatyce —
inaczej operator ustawia scenę pod inny obraz, niż zostanie zapisany.

## 5. Kontrakt akwizycji — weryfikacja po każdym ujęciu

Odczyt z JSON-a metadanych `rpicam-still` i porównanie z profilem
(`spec-analizy-barwy.md` §2.1):

| pole | reguła | reakcja na naruszenie |
|---|---|---|
| `ExposureTime` | = profil, ±1% | **odrzucenie** |
| `AnalogueGain` | = profil, ±1% | **odrzucenie** |
| `DigitalGain` | 1,000 ±0,01 | **odrzucenie** — ISP kompensował ekspozycję cyfrowo |
| `ColourGains` | = profil, ±1% | **odrzucenie** |
| `ColourCorrectionMatrix` | identyczna jak w pierwszym ujęciu sesji | **odrzucenie** |
| `Lux` | zapis, bez progu | ostrzeżenie przy zmianie > 5% w sesji |
| `SensorTemperature` (jeśli dostępna) | zapis, bez progu | — |

Odrzucenie oznacza: pliki trafiają do `rejected/<capture_id>/` razem z rekordem
przyczyny, licznik `frame_seq` **nie** jest inkrementowany, operator dostaje komunikat
z konkretną rozbieżnością. Nic nie jest kasowane — odrzucone ujęcie jest dowodem, że
stanowisko się rozjechało, i może być potrzebne przy diagnozie.

Program musi też sprawdzić, że parametry ISP z profilu **faktycznie zostały przekazane**
do `rpicam-still`. Ponieważ `--sharpness`, `--denoise`, `--saturation`, `--contrast`
i `--brightness` nie wracają w metadanych, jedyną możliwą weryfikacją jest zapisanie
pełnej linii polecenia i porównanie jej z profilem. To jest wymagane, nie opcjonalne.

## 6. Kontrola jakości ujęcia (QC) na miejscu

QC ma być tani — liczony na miejscu, w kilkaset milisekund, bez segmentacji. Wyniki
trafiają do `qc.json` przy każdym ujęciu.

| miara | jak liczona | próg alarmu | wartość odniesienia |
|---|---|---|---|
| `max_dn` | maksimum po kanałach | > 250 → odrzucenie | dziś 203; docelowo 220–230 |
| `clip_frac` | udział pikseli ≥ 250 DN | > 0 → odrzucenie | dziś 0,000% |
| `patch_present` | ROI wzorców z profilu: sd < 8 DN i pole > 90% ROI | brak → **odrzucenie** | — |
| `patch_L_white` | L\* mediana ROI bieli | \|Δ\| > 0,5 vs `expected` → ostrzeżenie | 69,82 |
| `patch_sd_L` | sd L\* w ROI bieli | > 1,5 → ostrzeżenie | 0,66 |
| `focus_metric` | wariancja laplasjanu w stałym ROI | spadek > 15% vs `expected` → **odrzucenie** | do zmierzenia |
| `foreground_frac` | udział pikseli powyżej progu Otsu | < 20% lub > 90% → ostrzeżenie | 57,9% |
| `mean_dn` | średnia kadru | \|Δ\| > 3% vs poprzednie ujęcie w sesji → ostrzeżenie | — |

Dwie z tych pozycji zasługują na komentarz, bo nie są oczywiste:

**`patch_present` jako warunek odrzucenia.** Jeśli wzorzec wypadnie z kadru albo zostanie
przysypany materiałem, zdjęcie traci kotwicę fotometryczną i nie da się go porównać
z resztą zbioru (`spec-analizy-barwy.md` §6.1). Wykrycie tego kosztuje jedno odchylenie
standardowe na wycinku 400×400 px — a niewykrycie kosztuje utratę całej próbki.

**`focus_metric`.** Rozjechana ostrość jest najczęstszym cichym uszkodzeniem takiego
stanowiska: nic nie sygnalizuje problemu, a wszystkie kolejne zdjęcia są nieporównywalne
z wcześniejszymi. Wariancja laplasjanu na stałym ROI jest tania i wystarczy do wykrycia
uderzenia w obiektyw. ROI musi być ustalone w profilu i **nie może obejmować wzorców**
(są gładkie) ani obszaru, w którym układ materiału się zmienia — najlepiej fragment
statycznego elementu sceny.

## 7. Ujęcia kalibracyjne i odniesienia

Osobny typ ujęcia, zapisywany w `calib/`, nie mieszany z materiałem pomiarowym.

| rodzaj | co to jest | kiedy | co daje |
|---|---|---|---|
| `flatfield` | jednorodna biała powierzchnia wypełniająca kadr, seria ≥ 10 ujęć uśrednionych | przy każdej zmianie profilu i raz na sesję | korekcja winietowania — obowiązkowa po przejściu na `imx477_scientific.json`, który nie zawiera bloku ALSC |
| `scale` | wzorzec wymiaru (linijka, szachownica) w płaszczyźnie materiału | przy każdej zmianie geometrii stanowiska | mm/px; dziś w `analiza/an3.py` jest **założenie** 35,9 µm/px, nie pomiar |
| `colorchart` | karta barw w scenie | raz na sesję | przeliczenie skali przyrządowej na kolorymetryczną, przenoszalność między stanowiskami |
| `dark` | zdjęcie przy zasłoniętym obiektywie, ten sam czas | raz na sesję | poziom ciemny i szum sensora |
| `reference_sample` | ustalona, niezmienna próbka materiału | **na początku i na końcu każdej sesji** | detektor dryfu w obrębie sesji i między sesjami (etap C protokołu) |

`reference_sample` jest tanim i mocnym zabezpieczeniem: jeśli ta sama fizyczna próbka
daje na początku i na końcu sesji istotnie różny wynik, cała sesja jest podejrzana i
wiadomo o tym od razu, a nie po miesiącach.

Program odmawia startu sesji pomiarowej, jeśli dla bieżącego profilu nie ma ważnego
`flatfield` i `scale` — chyba że operator jawnie wybierze tryb bez kalibracji, co jest
zapisywane w rekordzie każdego ujęcia sesji jako flaga, nie jako cicha domyślność.

## 8. Metadane wprowadzane przez operatora

Kamera nie zna kontekstu, a bez kontekstu zbiór jest bezużyteczny do wyznaczania progów.

**Na poziomie próbki (wymagane przed pierwszym ujęciem):**

| pole | typ | uwagi |
|---|---|---|
| `batch_id`, `sample_id` | str | patrz §2; wpisywane ręcznie. Pole ma przyjmować dowolny łańcuch i nie walidować formatu poza niepustością — dzięki temu ewentualne późniejsze wprowadzenie skanera kodów nie zmienia ani modelu danych, ani interfejsu |
| `supplier` | str | dostawca |
| `material_type` | słownik | typ materiału / frakcja |
| `expert_verdict` | enum: `OK` / `NOK` / `graniczny` / `nieoceniony` | **kluczowe dla etapu E protokołu** |
| `verdict_reasons` | lista ze słownika kontrolowanego | `za_ciemny`, `kremowy`, `zazolcony`, `zabrudzony`, `nieregularny_ksztalt`, `zla_frakcja`, `obcy_material`; wiele naraz. **Ten sam słownik jest zbiorem klas wtrąceń systemu operacyjnego** (`spec-operacyjny.md` §6.1, BR-015) — te etykiety są jednocześnie materiałem uczącym klasyfikatora i nazwami, którymi raportuje on wynik, więc rozjechanie się obu list unieważnia materiał uczący |
| `verdict_author` | str | kto ocenił |
| `verdict_date` | data | kiedy, jeśli inna niż data zdjęcia |
| `protocol_stage` | enum: `A` / `B` / `C` / `D` / `E` / `F` / `inne` | etap z `spec-analizy-barwy.md` §8 |
| `notes` | tekst | swobodny |

`verdict_reasons` musi pochodzić ze słownika kontrolowanego, a nie z pola tekstowego.
Przyczyny odrzucenia będą później zmienną objaśnianą przy dobieraniu progów; wpisane
swobodnie („trochę szare", „szarawe", „szare?") nie dadzą się zagregować.

Pole `expert_verdict = nieoceniony` jest dopuszczalne i uczciwe — ale program powinien
raportować na koniec sesji, ile próbek zostało bez oceny, bo to bezpośrednio ogranicza
przydatność zebranego materiału.

**Na poziomie sesji:** operator, oświetlacz (id), czas od jego włączenia, temperatura
otoczenia, uwagi o warunkach.

## 9. Wsparcie dla protokołu badawczego

Program ma znać protokół z `spec-analizy-barwy.md` §8 i prowadzić po nim operatora,
zamiast liczyć na to, że ten sam zapamięta liczby ujęć.

| etap | co program wymusza | domyślnie |
|---|---|---|
| A — powtarzalność ujęcia | seria ujęć bez przerwy, blokada deklaracji przesypania | 10 ujęć |
| B — powtarzalność ułożenia | wymuszony monit „przesyp materiał" między ujęciami | 10 ułożeń × 1 ujęcie |
| C — stabilność w czasie | `reference_sample` na starcie i końcu sesji, przypomnienie o kolejnej sesji | 10 sesji |
| D — materiał akceptowany | wymusza `expert_verdict = OK` | ≥ 20 próbek |
| E — materiał odrzucany | wymusza `expert_verdict ∈ {NOK, graniczny}` + niepustą listę przyczyn | ≥ 10 próbek |
| F — wzorce fizyczne | ujęcie `colorchart` w sesji | 1 na sesję |

Program pokazuje postęp badania: ile ujęć w każdym etapie już jest, ile brakuje.
To jest funkcja raportowa, nie blokująca — operator może odstąpić od planu, ale
odstępstwo ma być widoczne, a nie przypadkowe.

## 10. Format zapisu

```
<archiwum>/<study_id>/
  profile.json                 # §3, niezmienny w obrębie badania
  study.json                   # opis badania, słowniki kontrolowane, plan protokołu
  calib/<kind>_<id>/…          # ujęcia kalibracyjne (§7)
  captures/<capture_id>/
      capture.png              # bajt w bajt z rpicam-still, nigdy nie przekodowywane
      capture.dng              # archiwum RAW
      meta.json                # metadane rpicam-still + wzbogacenie (niżej)
      acquisition.json         # klucze, operator, werdykt, warunki, linia polecenia
      qc.json                  # miary z §6 i werdykt QC
      sha256sums.txt           # sumy wszystkich plików katalogu
  rejected/<capture_id>/…      # ujęcia odrzucone + przyczyna, ta sama struktura
  manifest.csv                 # jeden wiersz na capture, do szybkiego przeglądu
  journal.jsonl                # dziennik dopisywany, jedno zdarzenie na wiersz
```

**Wzbogacenie `meta.json`.** Do surowych metadanych `rpicam-still` program dopisuje pola
z przedrostkiem `_`, których kamera nie raportuje, a które `analiza3/measure.py` już dziś
czyta (§6 specyfikacji analizy):

```
_isp_sharpness, _isp_denoise, _isp_saturation, _isp_contrast, _isp_brightness,
_tuning_file, _tuning_file_sha256, _rpicam_version, _libcamera_version,
_profile_id, _command_line
```

Uwaga integracyjna: `measure.py` pobiera dziś ścieżkę pliku strojenia z argumentu
`--tuning-file`. Po wdrożeniu tego formatu należy go rozszerzyć tak, by preferował
`_tuning_file` i `_tuning_file_sha256` z `meta.json` — jedna zmiana, ale bez niej
suma kontrolna strojenia nie trafi do `capture.json` automatycznie.

**`manifest.csv`** — kolumny: `capture_id`, klucze z §2, `session_id`, `profile_id`,
`timestamp`, `expert_verdict`, `protocol_stage`, `qc_status`, `image_sha256`.
Manifest jest wygodą; źródłem prawdy są katalogi ujęć.

**`journal.jsonl`** — dopisywany, nigdy nie edytowany: start/koniec sesji, każde ujęcie,
każde odrzucenie z przyczyną, każda zmiana profilu, każde ujęcie kalibracyjne. Dziennik
jest tym, co pozwala odtworzyć historię stanowiska, gdy dane zaczną się nie zgadzać.

### 10.1 Pliki zamiast bazy — rekomendacja

**Zostajemy przy plikach.** Uzasadnienie, a nie tylko potwierdzenie założenia:

- Archiwum musi przeżyć program. Za dwa lata, przy wyznaczaniu progów, liczyć się będzie
  możliwość wzięcia katalogu i przeczytania go czymkolwiek. Katalog z PNG, DNG i JSON
  jest czytelny bez żadnego oprogramowania; plik bazy wymaga zgodnej wersji silnika.
- Jednostką pracy jest ujęcie, a ujęcie to i tak kilkadziesiąt megabajtów plików
  binarnych. Baza i tak przechowywałaby tylko ścieżki — czyli byłaby drugim, zdolnym
  do rozjechania się opisem tego samego.
- Skala nie wymusza bazy. Protokół z §9 to rząd kilkuset ujęć. Przeskanowanie kilkuset
  małych JSON-ów zajmuje ułamek sekundy, a `manifest.csv` i tak pełni rolę indeksu.
- Zapis jednym procesem, jeden operator, brak transakcji rozproszonych. Nie ma problemu,
  który baza rozwiązywałaby lepiej niż atomowe przemianowanie katalogu (§11).

**Kiedy to przemyśleć ponownie:** przy przekroczeniu ~10 000 ujęć w jednym archiwum albo
gdy pojawi się potrzeba złożonych zapytań w UI (filtrowanie po wielu polach naraz,
sortowanie po wynikach QC, korelacje między sesjami). Wtedy właściwym krokiem jest
**SQLite jako indeks pomocniczy, nigdy jako źródło prawdy** — plik `index.sqlite`
odtwarzalny w całości ze skanu archiwum jednym poleceniem, kasowalny bez straty danych.
Baza serwerowa (PostgreSQL i podobne) nie jest tu uzasadniona na żadnym etapie: dokłada
usługę do utrzymania na Pi i drugie miejsce, w którym dane mogą się rozejść z archiwum.

## 11. Integralność i odporność

- **Sumy kontrolne** liczone bezpośrednio po zapisie, przed pokazaniem operatorowi
  potwierdzenia. Niezgodność → ujęcie do kwarantanny.
- **Zapis atomowy**: katalog ujęcia powstaje pod nazwą tymczasową i jest przemianowany
  dopiero po komplecie plików i sumach. Przerwanie zasilania nie zostawia ujęcia
  wyglądającego na kompletne.
- **Miejsce na dysku**: kontrola przed każdym ujęciem. Budżet ~40 MB na ujęcie
  (PNG ~17 MB + DNG ~24 MB), czyli kilkaset ujęć protokołu to rząd 10–20 GB. Program
  odmawia startu sesji przy zapasie mniejszym niż 20 ujęć.
- **Kopia zapasowa**: polecenie kopiujące archiwum na nośnik zewnętrzny z weryfikacją
  sum kontrolnych i raportem różnic. Archiwum bez kopii jest jedną awarią karty SD
  od utraty całego badania.
- **Wznowienie**: przerwana sesja daje się wznowić z zachowaniem `layout_seq`
  i `frame_seq`; stan sesji trzymany w pliku, nie w pamięci procesu.

## 12. Interfejs webowy

Serwer działa na Raspberry Pi, przeglądarka na tablecie lub laptopie przy stanowisku,
w sieci lokalnej, bez internetu. Interfejs jest jedynym sposobem obsługi; tryb wsadowy
z linii poleceń zostaje wyłącznie do testów i skryptów.

### 12.1 Założenia projektowe

| założenie | konsekwencja |
|---|---|
| operator ma zajęte ręce materiałem | wielkie cele dotykowe, dwa przyciski dominujące ekran, żadnych okien modalnych na ścieżce ujęcia |
| kamera jest zasobem wyłącznym | podgląd na żywo i wykonanie zdjęcia nie mogą działać jednocześnie — patrz 12.9 |
| przeglądarka może się rozłączyć | stan sesji żyje w pliku na serwerze, nie w karcie przeglądarki |
| obraz waży ~17 MB | do przeglądarki idą pliki pochodne, nigdy archiwum — patrz 12.10 |
| jeden operator naraz | zapis do archiwum szeregowany; druga zakładka dostaje tryb tylko do odczytu |
| brak internetu | żadnych zewnętrznych zasobów, czcionek, CDN-ów |

Komunikaty muszą podawać **konkretną rozbieżność**, nie ogólnik: „ExposureTime 64998 µs,
profil wymaga 65000 µs ±650" zamiast „błąd parametrów".

### 12.2 Mapa ekranów

```
/                 pulpit — stan stanowiska, ostatnie sesje, start sesji
/session          ekran sesji (główny, tu spędza się 95% czasu)
/capture/<id>     weryfikacja pojedynczego ujęcia
/archive          przegląd i filtrowanie archiwum
/profile          parametry akwizycji: wgląd i zmiana
/profile/exposure asystent doboru czasu naświetlania
/calibration      ujęcia kalibracyjne (§7)
/report           postęp protokołu, dryf, odrzucenia
/diagnostics      wersje, miejsce na dysku, log, kopia zapasowa
```

### 12.3 Ekran sesji — główny

```
┌───────────────────────────────────────────────────────────────────────────┐
│ SESJA 20260808-1420 · profil P1-scientific · operator MM      ● kamera OK │
├──────────────────────────────────────┬────────────────────────────────────┤
│                                      │ PRÓBKA                    [zmień]  │
│                                      │ dostawa   D-2026-041               │
│         PODGLĄD NA ŻYWO              │ próbka    S-017                    │
│      (na parametrach profilu)        │ werdykt   NOK · kremowy            │
│                                      │ etap      E                        │
│                                      │ ułożenie  3        ujęcie  2       │
│                                      ├────────────────────────────────────┤
│                                      │  ┌──────────────────────────────┐  │
│                                      │  │       ZRÓB ZDJĘCIE           │  │
│                                      │  └──────────────────────────────┘  │
│                                      │  ┌──────────────────────────────┐  │
│                                      │  │    PRZESYPAŁEM MATERIAŁ      │  │
│                                      │  └──────────────────────────────┘  │
├──────────────────────────────────────┴────────────────────────────────────┤
│ OSTATNIE  L03F01 ✓ max 227 DN · biel L* 69,8 (Δ +0,1) · ostrość 100 %     │
│ L02F04 ✓   L02F03 ✓   L02F02 ✗ ostrość −22 %   L02F01 ✓                   │
└───────────────────────────────────────────────────────────────────────────┘
```

Rozdzielenie „ZRÓB ZDJĘCIE" i „PRZESYPAŁEM MATERIAŁ" na dwa osobne, wielkie przyciski
jest wymaganiem, nie sugestią estetyczną — to jedyne miejsce w całym systemie, gdzie
powstaje rozróżnienie na `frame_seq` i `layout_seq` (§2), a od niego zależy możliwość
rozłożenia wariancji na σ_frame i σ_layout.

Zachowanie:

- Wciśnięcie „ZRÓB ZDJĘCIE" blokuje oba przyciski do czasu werdyktu QC. Przycisk nie
  „mruga" — pokazuje etapy: *zatrzymanie podglądu → ekspozycja → zapis → QC*.
- Werdykt pojawia się na tym samym ekranie, bez przechodzenia dalej. Zielony pasek =
  zapisane; czerwony = odrzucone, z przyczyną i podpowiedzią, co zrobić.
- Odrzucenie **nie** zwiększa `frame_seq` — operator powtarza ujęcie i numeracja pozostaje
  ciągła (§5).
- Pasek historii pokazuje ostatnie kilkanaście ujęć sesji ze statusem; kliknięcie
  przenosi do weryfikacji (12.4).
- Zmiana próbki wymaga wypełnienia pól z §8 zanim odblokują się przyciski ujęcia.
- Etap protokołu steruje zachowaniem: w etapie A przycisk „PRZESYPAŁEM" jest zablokowany,
  w etapie B po każdym ujęciu pojawia się monit o przesypanie, w etapie E nie da się
  zapisać próbki bez niepustej listy przyczyn odrzucenia (§9).

**Wyzwalanie wyłącznie z ekranu.** Nie przewidujemy przycisku sprzętowego. Stąd wymóg
dużego celu dotykowego i odporności na przypadkowe podwójne kliknięcie: przycisk jest
zablokowany od momentu wciśnięcia do werdyktu QC, więc drugie dotknięcie nie tworzy
drugiego ujęcia. Wyzwolenie jest zwykłym wywołaniem `POST /api/capture` (§12.11), więc
dołożenie kiedyś wyzwalacza sprzętowego nie wymagałoby zmian poza samym sterownikiem.

### 12.4 Weryfikacja ujęcia

To jest druga połowa wymagania „łatwość robienia zdjęć i weryfikacji efektów". Ekran
ma odpowiadać na jedno pytanie: *czy to ujęcie nadaje się do analizy, a jeśli nie, to
dlaczego*.

| element | zawartość |
|---|---|
| obraz | podgląd z przełączanymi nakładkami: ROI wzorców, ROI ostrości, mapa pikseli ≥ 245 DN, siatka kafli pola oświetlenia |
| zoom 1:1 | wycinek w pełnej rozdzielczości, przesuwalny — do wzrokowej oceny ostrości i tekstury; bez tego nie da się ocenić, czy zdjęcie jest ostre |
| histogram | trzy kanały + luminancja, z zaznaczonym zakresem docelowym 220–230 DN i progiem przesterowania |
| tabela QC | każda miara z §6: wartość, próg, status, wartość odniesienia z profilu |
| wzorce | zmierzone L\*a\*b\* bieli i szarości, odchyłka od odniesienia profilu, sd |
| trendy sesji | przebiegi `patch_L_white`, `focus_metric`, `mean_dn` w czasie sesji — dryf widać na wykresie, nie w tabeli |
| porównanie | suwak/przełącznik między tym ujęciem a poprzednim oraz `reference_sample` sesji |
| metadane | pełny `meta.json`, `acquisition.json`, linia polecenia, sumy kontrolne |

Ujęcia odrzucone są dostępne z tego samego ekranu, wyraźnie oznaczone. Operator musi móc
zobaczyć, *co* zostało odrzucone — inaczej diagnoza problemu ze stanowiskiem jest zgadywaniem.

### 12.5 Przegląd archiwum

Lista ujęć z filtrowaniem po: dostawie, próbce, sesji, etapie protokołu, werdykcie
eksperta, statusie QC, zakresie dat. Widok kafelkowy z miniaturami i widok tabelaryczny.
Zaznaczone ujęcia można wyeksportować jako listę ścieżek do podania `analiza3/measure.py`.

Dane do listy pochodzą z `manifest.csv`; przycisk **przebuduj indeks** odtwarza go ze
skanu katalogów. Manifest jest wygodą, katalogi są prawdą (§10.1) — i UI ma to
egzekwować, a nie zacierać.

### 12.6 Profil i parametry

Wgląd: wszystkie pola profilu (§3) z wartościami, jednostkami i krótkim wyjaśnieniem,
co dany parametr robi. Osobno wyróżnione parametry ISP, których **nie da się zweryfikować
z metadanych** (`sharpness`, `denoise`, `saturation`, `contrast`, `brightness`) — przy
nich informacja, że jedynym dowodem ich ustawienia jest zapisana linia polecenia (§5).

Zmiana parametru:

1. Edycja odbywa się w kopii roboczej, nie na profilu aktywnym.
2. UI pokazuje **różnicę** wobec profilu aktywnego, pole po polu.
3. Wymagane jest uzasadnienie tekstowe.
4. Zatwierdzenie tworzy **nowy `profile_id`** i wymusza decyzję: nowe badanie czy
   rozgałęzienie istniejącego. Nadpisanie aktywnego profilu jest niemożliwe.
5. Ostrzeżenie wprost: zmiana pliku strojenia, czasu naświetlania lub wzmocnień
   unieważnia porównywalność z materiałem zebranym wcześniej.

Ta ścieżka jest celowo niewygodna. Zmiana parametru w trakcie badania to zdarzenie
kosztowne i UI ma to odzwierciedlać, zamiast pozwalać zrobić to jednym suwakiem.

**Asystent doboru czasu naświetlania** (`/profile/exposure`) — potrzebny, bo po przejściu
na `imx477_scientific.json` czas trzeba dobrać od nowa. Wykonuje serię ujęć próbnych
z drabinką czasów, dla każdego pokazuje `max_dn`, `clip_frac`, L\* wzorca bieli i histogram,
i proponuje wartość, przy której najjaśniejsze piksele sięgają 220–230 DN bez
przesterowania. Ujęcia próbne trafiają do `calib/exposure_<id>/`, nie do zbioru pomiarowego.

### 12.7 Kalibracja

Kreator dla każdego rodzaju z §7: instrukcja co ustawić w scenie, wykonanie serii,
podgląd wyniku, zapis z nadaniem identyfikatora i przypięciem do profilu. Dla flat-fielda
dodatkowo mapa niejednorodności i liczba `illum_range_p98_L` przed i po korekcji — czyli
wskaźnik, którym mierzy się skuteczność korekcji po utracie ALSC.

Widoczny stan: dla bieżącego profilu, która kalibracja jest, kiedy zrobiona, a której brak.
Brak `flatfield` lub `scale` jest wyświetlany jako ostrzeżenie na ekranie sesji przez
cały czas jej trwania, a nie tylko przy starcie.

### 12.8 Raport protokołu

Postęp każdego etapu A–F (§9): ile ujęć zebrano, ile brakuje, których próbek dotyczy.
Osobno: liczba próbek bez oceny eksperta — bo to bezpośrednio ogranicza przydatność
materiału do wyznaczenia progów. Lista odrzuceń z przyczynami, zagregowana po typie
(pozwala zauważyć, że np. 30% odrzuceń to ostrość, czyli stanowisko wymaga interwencji).

### 12.9 Podgląd na żywo a konflikt o kamerę

Kamera jest zasobem wyłącznym — `rpicam-still` nie wykona ujęcia, gdy strumień podglądu
trzyma urządzenie. Wymagania:

- Podgląd jako strumień MJPEG na parametrach profilu, w rozdzielczości zredukowanej.
  Podgląd na automatyce jest **niedopuszczalny**: operator ustawiałby scenę pod inny
  obraz, niż zostanie zapisany.
- Serwer zarządza kamerą przez jeden komponent szeregujący. Żądanie ujęcia: zatrzymanie
  podglądu → ujęcie → wznowienie podglądu, z pokazaniem stanu w UI.
- Przerwa jest widoczna dla operatora (1–2 s) i musi być zakomunikowana, a nie ukryta —
  zamrożona klatka bez informacji wygląda jak zawieszenie programu.
- Żądanie ujęcia w trakcie przejścia jest odrzucane z komunikatem, nie kolejkowane.

### 12.10 Pliki pochodne dla UI

Archiwum jest niezmienne (§0), więc wszystko, co UI potrzebuje do wyświetlania, powstaje
obok i jest kasowalne:

```
captures/<capture_id>/derived/
    preview_1600.jpg      podgląd do przeglądarki
    thumb_320.jpg         miniatura do list
    tiles/                kafle 1:1 do widoku zoom
    qc_overlay.png        nakładki (wzorce, ROI ostrości, mapa przesterowania)
    histogram.json        dane do wykresu
```

Katalog `derived/` można skasować w całości i odtworzyć z archiwum. Nie wchodzi do sum
kontrolnych ujęcia i nie jest kopiowany na nośnik zapasowy.

### 12.11 API

Serwer wystawia HTTP JSON; UI nie ma własnego stanu poza bieżącym widokiem.

| metoda | zasób | działanie |
|---|---|---|
| `POST` | `/api/session` | start sesji (operator, warunki) |
| `DELETE` | `/api/session` | zamknięcie sesji + raport |
| `PUT` | `/api/session/sample` | deklaracja próbki (§8) |
| `POST` | `/api/session/layout` | „przesypałem materiał" — `layout_seq += 1` |
| `POST` | `/api/capture` | wykonanie ujęcia; zwraca `capture_id` i werdykt QC |
| `GET` | `/api/capture/<id>` | rekordy, QC, ścieżki plików pochodnych |
| `GET` | `/api/captures?filtry` | lista do przeglądu |
| `GET` | `/api/profile`, `POST` `/api/profile/draft`, `POST` `/api/profile/commit` | §12.6 |
| `POST` | `/api/calibration/<kind>` | §12.7 |
| `GET` | `/api/report` | §12.8 |
| `GET` | `/api/preview.mjpg` | strumień podglądu |
| `GET` | `/api/events` | SSE: postęp ujęcia, wynik QC, zmiany stanu kamery |

Postęp ujęcia idzie strumieniem zdarzeń (SSE), a nie odpytywaniem — operator ma widzieć,
na którym etapie jest ujęcie, bez opóźnienia interwału odpytywania.

### 12.12 Błędy i rozłączenia

- Stan sesji (`session.json`) jest zapisywany po każdej zmianie. Odświeżenie strony,
  padnięcie przeglądarki albo przejście na inne urządzenie odtwarza ekran sesji
  z licznikami i próbką bez utraty kontekstu.
- Druga otwarta karta wykrywa aktywną sesję i przechodzi w tryb tylko do odczytu, żeby
  dwa urządzenia nie inkrementowały liczników.
- Awaria w trakcie zapisu ujęcia zostawia katalog tymczasowy, który przy starcie serwera
  jest przenoszony do `rejected/` z przyczyną `zapis niedokończony` (§11).
- Brak kamery, brak miejsca na dysku i niezgodna suma kontrolna pliku strojenia blokują
  możliwość wykonania ujęcia i są widoczne jako stały pasek stanu, a nie jednorazowy
  komunikat.

### 12.13 Stos technologiczny

**Backend: FastAPI (uvicorn), frontend: React.** Bundle React budowany na maszynie
deweloperskiej i serwowany statycznie przez FastAPI — na Pi nie ma nodejs ani kroku
budowania. Żadnych zasobów z sieci: czcionki, ikony i style wchodzą do bundla, bo
stanowisko pracuje offline.

Cztery ograniczenia wynikające z natury stanowiska, które trzeba uwzględnić w architekturze:

**Dokładnie jeden proces roboczy.** `uvicorn --workers 1`. Kamera, licznik ujęć i zapis do
archiwum są zasobami pojedynczymi; drugi proces roboczy oznaczałby dwa niezależne stany
sesji i możliwość równoległego wyzwolenia ujęcia. Skalowanie poziome jest tu nie tylko
niepotrzebne — jest szkodliwe.

**Wykonanie ujęcia blokuje na kilka sekund.** `rpicam-still` to podproces trwający 3–6 s.
Musi być uruchamiany poza pętlą zdarzeń (executor / wątek roboczy), inaczej strumień SSE
i reszta API zamierają na czas ujęcia — czyli dokładnie wtedy, gdy UI ma pokazywać postęp.
Sekwencja *zatrzymanie podglądu → ujęcie → QC → wznowienie podglądu* jest jedną operacją
szeregowaną przez wspólny zamek kamery (§12.9).

**Podgląd MJPEG jako `StreamingResponse`.** Strumień trzyma połączenie otwarte przez cały
czas trwania sesji, więc musi mieć własną obsługę rozłączenia i nie może blokować zamka
kamery dłużej, niż trwa pojedyncza klatka.

**Współdzielenie kodu z warstwą pomiarową.** Backend jest w Pythonie między innymi po to,
żeby liczenie QC (§6) korzystało z `analiza3/spec_common.py` — wykrywanie wzorców, maska
pierwszego planu i konwersja do CIELAB są już tam zaimplementowane i przetestowane. QC
w akwizycji i pomiar w analizie muszą liczyć te same wielkości tym samym kodem, inaczej
zaczną się rozjeżdżać.

Uwierzytelnianie nie jest wymagane w sieci izolowanej; tożsamość operatora jest wybierana
przy starcie sesji i służy do opisu danych, nie do kontroli dostępu. Jeśli stanowisko
trafi do sieci współdzielonej, wystarczy pojedynczy token — bez budowania systemu kont.

## 13. Wymagania niefunkcjonalne

- Działa na Raspberry Pi, w sieci lokalnej, bez internetu.
- Cykl ujęcia (wyzwolenie → potwierdzenie QC w przeglądarce) docelowo ≤ 8 s przy czasie
  65 ms. Wąskim gardłem jest kodowanie PNG 12 Mpx, zapis DNG i wygenerowanie plików
  pochodnych (§12.10), nie ekspozycja. Podgląd ujęcia w UI ma się pojawić przed
  zakończeniem generowania kafli zoomu — miniatura najpierw, reszta w tle.
- Przeglądarka: tablet lub laptop, ekran od 10", obsługa dotykiem. Bez wymagania
  najnowszej wersji przeglądarki i bez zewnętrznych zasobów.
- Nie wymaga uprawnień administratora poza dostępem do kamery.
- Konfiguracja w plikach tekstowych pod kontrolą wersji; żadnych wartości wpisanych
  na stałe w kodzie — to samo wymaganie, co w `wytyczne-ksztalty.md` §7.

## 14. Kryteria odbioru programu

| kryterium | sposób sprawdzenia |
|---|---|
| wymuszanie parametrów | 10 kolejnych ujęć → identyczne `ExposureTime`, `AnalogueGain`, `DigitalGain`, `ColourGains`, `ColourCorrectionMatrix` |
| wykrywanie naruszenia | ujęcie z celowo zmienionym czasem → odrzucone, z podaną rozbieżnością |
| wykrywanie braku wzorca | wzorzec zasłonięty → ujęcie odrzucone |
| wykrywanie rozjechanej ostrości | celowe rozogniskowanie → `focus_metric` poniżej progu, odrzucenie |
| poprawność liczników | scenariusz 3 ułożenia × 3 ujęcia → 9 ujęć o poprawnych `layout_seq`/`frame_seq` |
| integralność | przerwanie zasilania w trakcie zapisu → brak katalogu wyglądającego na kompletny |
| wznowienie | restart w połowie sesji → liczniki i stan zachowane |
| odporność UI | odświeżenie przeglądarki i przejście na inne urządzenie w trakcie sesji → ekran sesji odtworzony z licznikami i próbką |
| konflikt o kamerę | żądanie ujęcia w trakcie przełączania podglądu → odrzucone z komunikatem, kamera nie zostaje zablokowana |
| pliki pochodne | skasowanie całego `derived/` → UI odtwarza podglądy z archiwum, `sha256sums.txt` bez zmian |
| ochrona profilu | próba nadpisania aktywnego profilu → niemożliwa; zmiana tworzy nowy `profile_id` z uzasadnieniem |
| zgodność z warstwą 2 | `analiza3/measure.py` uruchomiony na wyjściu **bez** `--allow-missing-metadata` kończy się statusem kontraktu `ok` |

Ostatnie kryterium jest najważniejsze — to jest cały sens tego programu, wyrażony jako
jeden sprawdzalny warunek.

## 15. Czego ten dokument nie rozstrzyga

- Docelowej liczby próbek w etapach D i E; specyfikacja analizy podaje minima
  (≥ 20 i ≥ 10), ale rzeczywista potrzebna liczność wyjdzie dopiero z rozrzutu
  zmierzonego w etapach A–C.
