# Architektura – stan bazowy (baseline)

Projekt: stanowisko do analizy próbek kamyków „Kostka mati”
Stan na: 04.11.2026
Źródła: `PROJEKT_INFO.md`, `parametry_maszyny.json`, `klipper/printer.cfg`, `lista_zakupow.csv`, zrzuty z `zrzuty/`, odpowiedzi użytkownika z 04.11.2026 (w tym analiza kolizji w złożeniu i specyfikacja makr)

Dokument podsumowuje rozumienie mechaniki, geometrii i logiki sterowania przed rozpoczęciem prac programistycznych oraz wskazuje znalezione niespójności i otwarte pytania. Wszystkie wymiary w mm.

---

## 1. Struktura repozytorium

| Ścieżka | Zawartość |
|---|---|
| `PROJEKT_INFO.md` | Główna specyfikacja: mechanika, osie, cykl, elektronika |
| `parametry_maszyny.json` | Te same parametry w formie maszynowej (spójne z `.md`) |
| `klipper/printer.cfg` | Konfiguracja Klippera z interlockiem i makrami cyklu (KALIBRUJ, POMIAR, ruchy ręczne) – wygenerowana offline, nietestowana na sprzęcie |
| `klipper/printer_DRAFT.cfg` | Poprzedni szkic (historyczny, zastąpiony przez `printer.cfg`) |
| `lista_zakupow.csv` | Elementy niedrukowane ze statusem (jest / do kupienia / do potwierdzenia) |
| `CAD/` | Moduły `.f3d` (Fusion) i `.step` oraz `Stanowisko_zlozenie.step` |
| `zrzuty/` | 11 widoków PNG złożenia i detali (sprzed zmiany geometrii płyty z 04.11.2026) |
| `Solidworks-MCP/` | Zewnętrzne repo (alisamsam/Solidworks-MCP) – serwer MCP do sterowania SolidWorks 2026 przez COM; skonfigurowany w `.mcp.json` |
| `docs/` | Dokumentacja architektury (ten plik) |

Uwagi porządkowe:
- `.gitignore` zawiera wpisy dla ESP32/PlatformIO, które nie występują w projekcie, oraz ignoruje cały `/CAD/`.
- Pliki `.f3d` nie są czytelne dla SolidWorks; wymiana z SolidWorks odbywa się przez `.step` (import jako złożenie, bez historii operacji).
- `Solidworks-MCP/.env` jest śledzony w gicie i zawierał klucz API z repo autora (zakomentowany, w historii gita nadal obecny). Katalogu nie publikować w obecnej postaci.

## 2. Cel systemu

Przygotowanie próbki kamyków do fotografii: porcja wsypana do lejka zostaje rozprowadzona w jedną warstwę na polu 300 × 300 mm, sfotografowana dwiema kamerami z sufitu, a następnie zgarnięta do kieszeni nadmiaru. Analiza obrazu jest osobnym projektem – tutaj wystarczy dostarczyć zdjęcia z metadanymi (T, odległość kamera–płyta, frakcja, g, znacznik czasu).

## 3. Układ współrzędnych

- Początek (0, 0, 0): oś tylnego lewego słupka ramy, na poziomie podłoża.
- X – w prawo (słupki na x = 0 i 580); Y – od tyłu (silnik, rozprowadzacz) do przodu (drzwiczki); Z – w górę.
- Rama 600 × 600 × 850 (profile 2020, ściany i podwójny sufit z MDF). Dolna płyta sufitu przyjęta na z = 740 (niepotwierdzone).

## 4. Osie i napędy

### 4.1 Spychacz – zmienna `s`

| Parametr | Wartość |
|---|---|
| Definicja | przesunięcie suwaka od parkingu, + w stronę przodu (+Y) |
| Zakres programowy | −2 … 450 (−2 = zapas za parkingiem, potrzebny przy bazowaniu) |
| Twardy ogranicznik przedni | s = 450,3 – łącznik wózka opiera się o korpusy napinaczy pasków; wózek MGN12 zostaje 1,6 mm przed końcem szyny |
| Ograniczniki końców szyn | zamontowane |
| Pozycje | załadunek 0 · koniec rozgarniania 405 · parking 0 |
| Zgarniacz | x = 142…438, czoło na y = 72,7 + s, dolna krawędź z = 572 (stała) |
| Silnik | JK42HS40-0504 (NEMA17, 0,5 A/faza), run_current = 0,35 A |
| Przeniesienie | GT2 20T → pasek 110 mm (1:1) → wałek Ø8 → 2 × GT2 20T → 2 paski robocze |
| Kinematyka | rotation_distance = 40 → 80 kroków/mm (16 µkroków) |
| Prędkość | ≥ 45 mm/s (450 mm w ≤ 10 s); obciążenie bardzo małe |

### 4.2 Stół – zmienna `T`

| Parametr | Wartość |
|---|---|
| Definicja | wysokość górnej powierzchni płyty nad podłożem |
| Zakres mechaniczny | 177 … 589; twardy ogranicznik dolny T ≈ 173,5 |
| Zakres programowy | 177 … 572 (T = 572 – szczelina zerowa pod zgarniaczem); w Klipperze `position_min: 150` wyłącznie na potrzeby bazowania, zakres roboczy pilnują makra |
| Maks. T przy rozgarnianiu | 571,5 (g ≥ 0,5) |
| Szczelina pod zgarniaczem | g = 572 − T; zalecane g ≈ 1,0…1,5 × wielkość ziarna |
| Wysokość do zdjęć | T = 177…240 → odległość kamera–płyta 563…500 mm |
| Napęd | 1 × JK42HS40-0504 (NEMA17, 12 V, 0,5 A/faza, 0,43 N·m), run_current = 0,35 A → pasek 1050 mm → 2 śruby T8 (1:1) |
| Kinematyka | śruba T8 × 2 (skok 2 mm) → rotation_distance = 2 → 1600 kroków/mm (16 µkroków) |
| Prędkość | ok. 10 mm/s = 300 obr/min silnika (pełny skok ≈ 40 s) – do weryfikacji na sprzęcie |
| Hamowanie | T8 × 2 jest w praktyce samohamowna (kąt wzniosu ≈ 5°); stół nie opada po wyłączeniu silnika |

### 4.3 Płyta stołu

- MDF 400 × 400 × 10 bez wycięć: y = 35…435 (x = 90…490 – przyjęte, do potwierdzenia).
- Przód płyty (y = 435…490): dwie drukowane części z otworem kieszeni nadmiaru x = 140…440, y = 445…485; pod nim wyjmowane pudełko ~430 ml.
- Ścianki: 4 narożniki w kształcie L, przykręcone przez ramy narożne do belek wózka stołu; górna krawędź na T + 40. Tylna ścianka y = 38…42 (za czołem zgarniacza na parkingu, y = 72,7), przednia ok. y = 486, boczne x = 140 / 440.
- Obszar pomiaru: x = 140…440, y = 140…440. Strefa załadunku: od czoła zgarniacza na parkingu (y = 72,7) do y = 140.

### 4.4 Rozprowadzacz (pasywny)

- Lejek ~360 ml nad obudową; próbka do ~250 ml jednej frakcji, ziarna 1 mm … 3 cm.
- Kanały 1 → 2 → 4 i pole kołków; dolna krawędź z = 645; wylot na szerokości x = 140…440 w strefie y = 120…156.
- Kamyki spadają pasem przed zgarniaczem stojącym w pozycji załadunku = parking (czoło na y = 72,7 przy s = 0).
- Czas spływu zależy od frakcji – do wyznaczenia doświadczalnie.

### 4.5 Reguły ruchu (zweryfikowane analizą kolizji w złożeniu)

| Wysokość stołu | Dozwolony ruch spychacza | Przyczyna ograniczenia |
|---|---|---|
| T ≤ 530 | s = 0 … 450 | brak |
| 530 < T ≤ 571,5 | s = 0 … 405 | od s ≈ 413 zgarniacz uderza w przednią ściankę i ramę |
| 571,5 < T ≤ 572 | nie rozgarniać | zgarniacz trze o płytę (g < 0,5) |

- Tylna ścianka nie ogranicza ruchu – zgarniacz w całym zakresie pracy nigdy jej nie przecina.
- Reguła obowiązuje w obie strony: przy s > 405 stół nie może wjechać powyżej T = 530.
- Przed powrotem na parking stół zjeżdża o **10 mm** (makro `POMIAR`; wartość dla obecnego, jednego rozmiaru ziaren – zmienić przy innym rozmiarze), żeby zgarniacz nie ciągnął warstwy z powrotem – wymóg technologiczny, nie kolizyjny.
- Interlock w `printer.cfg`: makra `_RUCH_STOL` i `_RUCH_SPYCHACZ` sprawdzają przed **każdym** ruchem zakres osi i regułę kolizyjną na podstawie bieżącej pozycji drugiej osi (tolerancja 0,01 mm). Naruszenie → `action_raise_error`, ruch nie zostaje wykonany.

### 4.6 Blokada stanu (`STAN_SYSTEMU`)

| Zmienna | Znaczenie |
|---|---|
| `zajety` | 1 = trwa makro ruchu. Każde makro użytkownika najpierw wywołuje `_ZAJMIJ` (sprawdza `zajety == 0`, ustawia 1), na końcu `_ZWOLNIJ` (`M400`, ustawia 0). |
| `skalibrowany` | 1 = pozycje osi są wiarygodne (po `KALIBRUJ`). Wymagane przez `PRZYGOTUJ`, `POMIAR` i ruchy ręczne. Kasowane przez `ODBLOKUJ`, `idle_timeout` i restart Klippera. |
| `przygotowany` | 1 = stół na wysokości załadunku po `PRZYGOTUJ`. Wymagane przez `POMIAR`; kasowane przez `POMIAR`, ruchy ręczne stołu, `KALIBRUJ`, `ODBLOKUJ`, `idle_timeout`. |
| `t_zaladunku` | T ustawione przez `PRZYGOTUJ` – na tej wysokości `POMIAR` rozgarnia. |

- Błąd w trakcie makra przerywa je i zostawia `zajety = 1` – system jest zablokowany do czasu `ODBLOKUJ`, które kasuje też kalibrację (wymagane ponowne `KALIBRUJ`).
- Klipper wykonuje G-code sekwencyjnie, więc dwa makra nie mogą realnie działać równocześnie; flaga działa przede wszystkim jako **zatrzask po błędzie** i sygnał stanu dla aplikacji (odczyt przez Moonraker: `gcode_macro STAN_SYSTEMU`).
- Bezpośrednie komendy `MANUAL_STEPPER` omijają interlock i blokadę – aplikacja ma używać wyłącznie makr.

## 5. Cykl pracy i makra (`klipper/printer.cfg`)

### 5.1 KALIBRUJ – bazowanie bezczujnikowe (StallGuard)

1. `_ZAJMIJ` (bez wymogu kalibracji), `skalibrowany = 0`.
2. **Stół**: `SET_POSITION=572` → jazda w dół z 5 mm/s do `MOVE=150 STOP_ON_ENDSTOP=1` (droga 422 mm ≥ maks. droga mechaniczna 415,5 mm) → po zatrzymaniu na oporze `SET_POSITION=173.5` → odjazd na T = 177. Ruch w dół jest zawsze bezpieczny, niezależnie od położenia spychacza.
3. **Warunek**: bazowanie spychacza tylko przy T ≤ 530 (sprawdzane; po kroku 2 T = 177).
4. **Spychacz**: `SET_POSITION=-2` → jazda w stronę +s z 20 mm/s do `MOVE=450 STOP_ON_ENDSTOP=1` (droga 452 mm) → po zatrzymaniu na korpusach napinaczy (fizycznie s = 450,3) `SET_POSITION=450` → odjazd na parking s = 0.
5. `skalibrowany = 1`, `_ZWOLNIJ`.

`STOP_ON_ENDSTOP=1` zwraca błąd, jeśli opór nie zostanie wykryty na całej drodze → makro przerwane, system zablokowany (bezpieczne).

### 5.2 Ruchy ręczne stołu

`GORA_5MM`, `DOL_5MM`, `GORA_1MM`, `DOL_1MM` – wymagają kalibracji, blokują system na czas ruchu, cel = bieżące T ± krok, prędkość 5 mm/s. Cel kroku jest walidowany **przed** zajęciem blokady (zakres [177, 572] i T > 530 przy s > 405) – odrzucony krok zgłasza błąd, ale nie blokuje systemu. Sam ruch przechodzi dodatkowo przez `_RUCH_STOL`.

### 5.3 PRZYGOTUJ – pozycja załadunku

Kamyki muszą mieć najkrótszą drogę zsypu, dlatego stół podczas wsypywania stoi na **najwyższej dozwolonej wysokości**, która jest jednocześnie wysokością rozgarniania:

- T_załadunku = 572 − g = **571,5** (g = 0,5 mm, minimum) → spadek z wylotu rozprowadzacza (z = 645) tylko **73,5 mm** (przy T = 177 byłoby 468 mm).
- Wyżej nie wolno: T = 572 to szczelina zerowa, a g ≥ 0,5.
- Brak kolizji: góra ścianek T + 40 = 611,5 < 617 (belka spychacza) < 645 (rozprowadzacz).
- Spychacz na s = 0: czoło zgarniacza na y = 72,7, za pasem zsypu (y = 120…156); T = 571,5 > 530 przy s = 0 ≤ 405 – interlock OK.
- Stół nie rusza się między wsypaniem a rozgarnianiem – ułożenie próbki nie jest zaburzane.

Sekwencja: spychacz → s = 0 (najpierw, dozwolone przy każdym T) → stół → T_załadunku → `t_zaladunku` zapisane w `STAN_SYSTEMU`, `przygotowany = 1`. Parametr opcjonalny `SZCZELINA` (domyślnie 0,5, min. 0,5).

Kolejność w aplikacji: `PRZYGOTUJ` → użytkownik wsypuje próbkę i potwierdza na ekranie, odczekanie na spływ → `POMIAR`.

### 5.4 POMIAR – rozgarnianie, powrót, zdjęcia

Wymaga `przygotowany = 1` (inaczej błąd bez ruchu i bez blokady). Na starcie kasuje `przygotowany` – każdy kolejny pomiar wymaga nowego `PRZYGOTUJ`. Parametr opcjonalny `SPEED` rozgarniania (domyślnie 45 mm/s).

| Krok | Ruch | Sprawdzenie interlocku |
|---|---|---|
| 1. Kontrola pozycji | spychacz → s = 0, stół → T_załadunku (po `PRZYGOTUJ` bez ruchu) | OK |
| 2. Rozgarnianie | spychacz 0 → 405 (45 mm/s) na T = 571,5 | s = 405 ≤ 405 przy T = 571,5 – OK (granica; kolizja fizyczna od s ≈ 413, zapas 8 mm) |
| 3. Powrót | stół → T = 561,5 (−10 mm) | T = 561,5 > 530 przy s = 405 ≤ 405 – OK |
| | spychacz → s = 0 | OK |
| 4. Zdjęcia | stół → T = 177 – **zmienna T do zdjęć do weryfikacji i dostrojenia po testach** | OK |

Odjazd 10 mm jest dobrany dla obecnego, jednego rozmiaru ziaren – przy innym rozmiarze zmienić `_KONFIG.t_odjazd_przed_powrotem` (odjazd musi być większy od ziarna; dla ziaren do 30 mm ok. 40 mm). Komentarz w kodzie.

Szacowany czas: `PRZYGOTUJ` ok. 40 s (z T = 177), `POMIAR` ok. 9 + 1 + 7 + 38 s ≈ 55 s. Zdjęcia wykonuje aplikacja na RPi po zakończeniu makra; LED włączane ręcznie.

Ręczny ruch stołu (`GORA_*` / `DOL_*`) kasuje `przygotowany` – wysokość załadunku przestaje być pewna, przed `POMIAR` trzeba ponownie wykonać `PRZYGOTUJ`.

### 5.5 Szczelina a wielkość ziarna (na przyszłość)

Obecnie obsługiwany jest **jeden rozmiar ziaren**: szczelina stała `szczelina_domyslna` (0,5 mm) i odjazd 10 mm. Zależność g = wsp × d (wsp = 1,0…1,5) jest przygotowana w `printer.cfg`, ale **zakomentowana**: zmienne `rozmiar_ziarna` i `wsp_szczeliny` w `_KONFIG` oraz linia oznaczona NA PRZYSZLOSC w makrze `PRZYGOTUJ`. Linie z `#` usuwa parser konfiguracji Klippera, więc zakomentowany kod Jinja nie jest wykonywany.

### 5.6 Pozostałe makra

- `STAN_SYSTEMU` – raport (zajętość, kalibracja, gotowość do załadunku, T, s).
- `ODBLOKUJ` – reset blokady po błędzie; kasuje kalibrację.

Warunki bezpieczeństwa: T ∈ [177, 572]; s ∈ [−2, 450]; T > 530 ⇒ s ≤ 405; s > 405 ⇒ T ≤ 530; szczelina ≥ 0,5 mm; bazowanie spychacza tylko przy T ≤ 530; kolejność bazowania: stół → spychacz.

## 6. Elektronika i oprogramowanie

- **Raspberry Pi 5 (≥ 8 GB)** – logika cyklu, UI na ekranie dotykowym, 2 kamery CSI (rozstaw 100 mm, w osi x = 290, y = 290), zapis zdjęć.
- **Kamery**: 2 × Raspberry Pi HQ Camera (Sony IMX477, 12,3 Mpx, matryca 6,29 × 4,71 mm, mocowanie CS) z obiektywem Arducam LN040 – CS 12 mm, ręczna regulacja ostrości. RPi 5 ma złącza CSI 22-pin – potrzebne taśmy 22/15 pin.
- **Ekran**: Waveshare 8″ IPS 1280 × 800, pojemnościowy, obraz przez HDMI (RPi 5: micro-HDMI), dotyk przez USB.
- **BigTreeTech SKR Mini E3 V3.0** (STM32G0B1, 4 × TMC2209 UART), USB do RPi.
- **Klipper + Moonraker** – obie osie jako `manual_stepper` przy `kinematics: none`; aplikacja steruje przez API Moonraker (JSON-RPC/HTTP).
- Przypisanie gniazd: spychacz → X, stół → Z; Y i E wolne; Z-STOP wolny (możliwa krańcówka stołu).
- Bazowanie bez krańcówek (StallGuard TMC2209) – decyzja użytkownika. Spychacz bazuje na ograniczniku przednim (s = 450,3).
- **LED**: sterowane ręcznie przełącznikiem, poza oprogramowaniem (brak wyjścia w Klipperze / GPIO).

### 6.1 Pole widzenia kamer (IMX477 + 12 mm)

| Odległość obiektyw–płyta | Pole widzenia jednej kamery |
|---|---|
| 563 mm (T = 177) | ≈ 295 × 221 mm |
| 500 mm (T = 240) | ≈ 262 × 196 mm |

Jedna kamera nie obejmuje pola 300 × 300. Dwie kamery w rozstawie 100 mm pokrywają je tylko łącznie i tylko przy odpowiedniej orientacji matryc (krótszy bok wzdłuż rozstawu: ≈ 321 × 295 mm przy 563 mm – nadal o 5 mm za mało w jednym kierunku). Rzeczywista odległość jest mniejsza o wysunięcie obiektywu pod sufit. Ostrość ustawiana ręcznie → zmiana T wymaga ponownego ostrzenia.

## 7. Konfiguracja Klippera (`klipper/printer.cfg`)

Zgodne z pinoutem SKR Mini E3 V3:
- X (spychacz): step PB13, dir PB12, enable PB14; Z (stół): step PB0, dir PC5, enable PB1.
- UART PC11/PC10, adresy X = 0, Z = 1; DIAG X = PC0, Z = PC2.

Kluczowe ustawienia:

| Parametr | Spychacz | Stół |
|---|---|---|
| `rotation_distance` | 40 | 2 (T8 × 2) |
| `run_current` | 0,35 A | 0,35 A |
| `position_min` / `position_max` | −2 / 450 | 150 (tylko bazowanie) / 572 |
| `velocity` / `accel` | 60 / 500 | 10 / 50 |
| `driver_SGTHRS` | 80 (do kalibracji) | 60 (do kalibracji) |

- `[mcu] serial: /dev/serial/by-id/DO_UZUPELNIENIA_PO_PODLACZENIU` – uzupełnić po podłączeniu (`ls /dev/serial/by-id/`).
- Wszystkie liczby cyklu w jednym makrze `_KONFIG` (zakresy, interlock, pozycje, prędkości, bazowanie).
- Dodane sekcje wymagane przez Moonraker: `[virtual_sdcard]`, `[display_status]`, `[pause_resume]`, oraz `[respond]`.
- `idle_timeout` (3600 s): wyłącza silniki i kasuje `skalibrowany`.

Do weryfikacji przy uruchomieniu:
- Nazwa pinu `tmc2209_<nazwa>:virtual_endstop` dla `manual_stepper` oraz czy bazowanie `STOP_ON_ENDSTOP` aktywuje StallGuard (TCOOLTHRS) dla `manual_stepper`.
- Dostępność `printer["manual_stepper <nazwa>"].position` w używanej wersji Klippera (interlock z niej korzysta).
- Obsługa `position_min` / `position_max` w `[manual_stepper]` (nowsze wersje Klippera).
- Kierunki `dir_pin` (+s do przodu, +T w górę) – sprawdzić krótkimi ruchami przed pierwszym `KALIBRUJ`.
- Kalibracja `driver_SGTHRS` obu osi.

### 7.1 Weryfikacja założeń z parametrami maszyny

| Założenie | Wynik | Uwagi / co zrobiono |
|---|---|---|
| `rotation_distance: 2` dla T8 × 2 | ✔ zgodne | 1600 kroków/mm; 10 mm/s = 16 000 kroków/s – w zasięgu SKR Mini E3 V3. |
| `run_current: 0.35` przy 0,5 A/faza | ✔ zgodne | 70 % prądu znamionowego (RMS). Mniejszy moment niż przy 0,38 A – sprawdzić stół przy 10 mm/s. |
| Zakres T [177, 572] | ✔ zgodne | 572 = szczelina zerowa; mechanicznie do 589. |
| Zakres s [−2, 450] | ✔ zgodne | Twardy ogranicznik 450,3 leży poza zakresem programowym (zapas 0,3 mm). |
| Interlock 530 / 405 | ✔ zgodne | Kolizja fizyczna od s ≈ 413 → zapas 8 mm. Wszystkie kroki `PRZYGOTUJ` i `POMIAR` przechodzą interlock (p. 5.3–5.4). |
| Bazowanie spychacza od `SET_POSITION=0` do 450 | ✘ **poprawione** | Ze stanu na parkingu (s = 0) droga 450 mm nie dociera do oporu (450,3) → `STOP_ON_ENDSTOP=1` zgłosiłby błąd. Użyto `SET_POSITION=-2` (droga 452 mm). Spychacz cofnięty za s ≈ −1,7 trzeba podsunąć ręcznie. |
| Bazowanie stołu od `SET_POSITION=572` do oporu 173,5 | ✘ **poprawione** | Przy `position_min: 177` ruch poniżej 177 byłby odrzucony; maks. droga mechaniczna to 415,5 mm. Ustawiono `position_min: 150` (droga 422 mm); zakres roboczy 177…572 pilnują makra. |
| Szczelina 0,5 mm (T = 571,5) | ⚠ do dobrania | Obecnie jeden rozmiar ziaren, szczelina stała. Zależność g ≈ 1,0…1,5 × d przygotowana w kodzie jako zakomentowana (p. 5.5). Przy g = 0,5 mm na płycie zostaną tylko ziarna ≤ 0,5 mm – wartość dobrać do obecnej frakcji (`PRZYGOTUJ SZCZELINA=<mm>` lub `_KONFIG.szczelina_domyslna`). |
| Odjazd stołu o 10 mm przed powrotem | ✔ ustalone | Wartość dla obecnego, jednego rozmiaru ziaren (decyzja użytkownika). Komentarz w kodzie: zmienić przy innym rozmiarze ziaren. |
| Wysokość załadunku | ✔ **poprawione** | Dodano makro `PRZYGOTUJ`: wsypanie przy T = 571,5 (najwyżej, jak pozwala mechanika) → spadek 73,5 mm zamiast 468 mm. `POMIAR` wymaga wcześniejszego `PRZYGOTUJ` (p. 5.3). |
| T = 177 do zdjęć | ⚠ do dostrojenia | Odległość ok. 563 mm; pole widzenia jednej kamery ≈ 295 × 221 mm (p. 6.1); ostrość ręczna. Oznaczone w kodzie komentarzem. |
| Blokada `zajety` | ✔ wdrożone, z zastrzeżeniem | Klipper wykonuje G-code sekwencyjnie – flaga działa głównie jako zatrzask po błędzie (p. 4.6). |
| Interlock bez kalibracji | ✘ **uzupełnione** | Przed `KALIBRUJ` pozycje są fikcyjne, więc interlock nie chroni. Dodano flagę `skalibrowany` wymaganą przez `PRZYGOTUJ`, `POMIAR` i ruchy ręczne. |
| Zakomentowany kod Jinja | ✔ sprawdzone | Linie z `#` są usuwane przez parser konfiguracji Klippera przed renderowaniem – zakomentowana formuła szczeliny nie jest wykonywana. Komentarz blokowy Jinja `{# … #}` nie działa (parser usuwa linię zamykającą), dlatego nie został użyty. |

## 8. Ryzyka

| Ryzyko | Opis | Działanie |
|---|---|---|
| Kolizja zgarniacza z przednią ścianką i ramą | Przy T > 530 i s ≳ 413 zgarniacz uderza w przednią ściankę płyty i ramę. | Interlock `_RUCH_STOL` / `_RUCH_SPYCHACZ` przed każdym ruchem (p. 4.5); koniec rozgarniania s = 405. |
| Bazowanie spychacza przy wysokim stole | Dojazd do ogranicznika (s = 450,3) przy T > 530 = kolizja. | Zawsze najpierw bazowanie stołu w dół; bazowanie spychacza tylko przy T ≤ 530. |
| Zawodny StallGuard stołu | Śruby trapezowe T8 × 2 (duże przełożenie) tłumią sygnał przeciążenia jeszcze silniej niż T8 × 8. | Niski prąd i prędkość, limit długości ruchu; alternatywnie krańcówka na Z-STOP. |
| Prędkość stołu | T8 × 2 przy 10 mm/s wymaga 300 obr/min; JK42HS40-0504 (uzwojenie 12 V, 0,5 A) traci moment przy wyższych obrotach. | Sprawdzić na sprzęcie; w razie gubienia kroków obniżyć prędkość lub zasilać 24 V. |
| Szczeliny boczne zgarniacza | Zgarniacz (x = 142…438) węższy o 2 mm z każdej strony od obszaru ścian (140…440). | Sprawdzić przeciekanie frakcji ~1 mm. |
| Pole widzenia kamer | Obiektyw 12 mm daje ≈ 295 × 221 mm na kamerę przy 563 mm; pole 300 × 300 nie jest w pełni pokryte (p. 6.1). Górna część wymaganego zakresu 500…700 mm nieosiągalna. | Ustalić rolę kamer i ich orientację; ewentualnie krótsza ogniskowa lub wyższy sufit. |
| Ostrość ręczna | Zmiana wysokości zdjęć T rozostrza obraz. | Robić zdjęcia na stałej, skalibrowanej wysokości T. |

## 9. Otwarte pytania

1. Rzeczywista wysokość dolnej płyty sufitu (przyjęto 740 mm) oraz wysunięcie obiektywu pod nią – wyznacza odległość kamera–płyta i pole widzenia.
2. Pokrycie pola 300 × 300 przez kamery (jedna kamera 12 mm ≈ 295 × 221 mm przy 563 mm): czy obrazy z dwóch kamer są sklejane, czy pełnią inną rolę (np. stereo)? Jaka orientacja matryc względem rozstawu 100 mm? Czy dopuszczalny obiektyw o krótszej ogniskowej?
3. Czy zdjęcia mają być wykonywane na jednej, stałej wysokości T (ostrość ustawiana ręcznie)?
4. Czy przed zdjęciem aplikacja ma prosić użytkownika o włączenie LED (komunikat + potwierdzenie na ekranie)?
5. Napięcie zasilania silników (12 czy 24 V) i akceptowalny czas ruchu stołu (T8 × 2: 10 mm/s = 300 obr/min).
6. Tablica: frakcja → szczelina g → prędkość rozgarniania (do wyznaczenia doświadczalnie) – etap przyszły, przy obsłudze wielu rozmiarów ziaren.
7. Czas spływu próbki przez rozprowadzacz.
8. Czy szczelina 2 mm po bokach zgarniacza jest celowa (również po przebudowie ścianek na narożniki L)?
9. Potwierdzenie wymiarów przyjętych bez danych: zakres x płyty MDF (90…490), położenie przedniej ścianki (y ≈ 486), koniec szyny MGN12 (z nowych danych ≈ 451,9; wcześniej podawano s ≈ 454,6).
10. Numery wersji modeli Fusion po zmianie geometrii oraz czy pliki STEP w `CAD/` zostały zaktualizowane.
11. Jaki jest obecny (jedyny) rozmiar ziaren d? Według g ≈ 1,0…1,5 × d szczelina powinna wynosić ok. d…1,5 d – obecna wartość domyślna 0,5 mm do potwierdzenia lub zmiany.

## 10. Narzędzia CAD

- Modele źródłowe: Autodesk Fusion (Stanowisko v20, obudowa v2, Zbieracz v12, Stol v12, Rozprowadzacz v3) – stan sprzed zmian geometrii płyty z 04.11.2026; nowe numery wersji do uzupełnienia.
- SolidWorks 2026 (wersja PL) dostępny przez serwer MCP (`.mcp.json` → `Solidworks-MCP/solidworks_mcp_server.py`): tworzenie części i szkiców, wyciągnięcia/wycięcia, import STEP z `CAD/`.
- Znane ograniczenia serwera: `list_features` zaniża liczbę operacji; wycięcia należy szkicować na ścianie bryły (`create_sketch_on_face`).
