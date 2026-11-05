# UI stanowiska „Kostka mati” — projekt

Data: 2026-11-05. Status: do akceptacji.

## 1. Po co to jest

Robotnik bez wiedzy technicznej ma przy maszynie wykonać pomiar próbki, klikając na ekranie
dotykowym Waveshare 8″ 1280 × 800. Maszyna rozgarnia próbkę, robi zdjęcie, wysyła je na osobny
serwer z GPU, a robotnik czeka na ekranie na wynik.

Na tym etapie celem jest przeklikiwalny i testowalny cały przebieg. Maszyna nie była jeszcze
uruchamiana, a system nie ma progów oceny, więc wynik analizy jest atrapą.

## 2. Cele, poza zakresem, porażki

**Cele**
- Pełny przebieg od włączenia maszyny do wyniku, prowadzony krok po kroku.
- Praca na prawdziwym sprzęcie po zmianie konfiguracji, bez przebudowy ekranu.
- Docker pod serwer z GPU, gotowy na podłączenie prawdziwego modelu.
- Cały przebieg uruchamialny na zwykłym komputerze, bez maszyny, kamery i GPU.

**Poza zakresem**
- Rejestracja dostaw, reguła 2 z 3, próbki kontrolne, operatorzy.
- Panel laboratorium, baza danych i archiwum na serwerze, TLS i klucze stacji, e-maile.
- Prawdziwy model analizy, progi oceny, walidacja jakości zdjęcia.
- Druga kamera, sterowanie LED, instalacja trybu kiosk na Pi.
- Zmiany w `docs/printer.cfg`.

**Co byłoby porażką, nawet jeśli działa**
- Robotnik musi znać nazwy makr albo sam decydować o kolejności kroków.
- Da się pominąć kalibrację po restarcie.
- Wynik atrapy można wziąć za prawdziwy.
- Aplikacja wysyła do maszyny coś poza makrami z listy (§5).
- Zdjęcie przepada, bo serwer był niedostępny.

## 3. Decyzje użytkownika

- Ekran 1280 × 800, układ **krok po kroku**: jedno polecenie i jeden duży przycisk.
- **Kalibracja zawsze po restarcie**, np. po wyłączeniu maszyny.
- Zdjęcia idą na **osobny serwer z GPU**, przygotowany pod Dockera.
- **Jedna kamera** na razie.
- Robotnik **czeka na wynik** na ekranie.
- Wynik analizy jest na razie **atrapą**.
- Skanowanie kodu ma być **możliwe, ale domyślnie wyłączone**; próbki **numerują się same, co 1**.
- **Po STOP wznawia robotnik**, świadomie; maszyna nigdy nie rusza sama.
- **Po przerwanym cyklu czyszczenie jest wymuszane**; robotnik nie musi o nim pamiętać.
- **Co N pomiarów ekran blokuje pracę poleceniem opróżnienia pudełka**; na start N = 1.
- Maszyna działa według `docs/opis_software.md` i `docs/architecture_baseline.md`.

## 4. Przebieg na ekranie

STOP jest widoczny na każdym ekranie, także w trakcie ruchu. Tryb serwisowy jest poza głównym
przebiegiem.

| # | Ekran | Co widzi robotnik | Co robi aplikacja | Przejście |
|---|---|---|---|---|
| 1 | Brak połączenia | „Brak połączenia z maszyną” | Ponawia połączenie z Moonrakerem | Stan `ready` → 2 lub 3; stan `shutdown` → Zatrzymana |
| — | Zatrzymana | „Maszyna zatrzymana. Sprawdź, czy nic jej nie blokuje i czy nikt nie ma rąk w środku”, przycisk „Wznów” przytrzymywany 3 s | `printer.firmware_restart`, oczekiwanie na `ready` | Gotowość → 2, potem czyszczenie |
| 2 | Kalibracja | „Potrzebna kalibracja”, przycisk KALIBRACJA, potem „Trwa kalibracja” | `KALIBRUJ` | Sukces → 3 |
| 3 | Gotowa | Numer następnej próbki, przycisk NOWY POMIAR | Przy włączonym skanowaniu najpierw pole kodu | Naciśnięcie → 4 |
| 4 | Przygotowanie | „Maszyna się przygotowuje” | `PRZYGOTUJ` | Sukces → 5 |
| 5 | Wsyp próbkę | „Wsyp próbkę do lejka”, PRÓBKA WSYPANA, Anuluj | Czeka na potwierdzenie | Potwierdzenie → 6; Anuluj → 2 (`KALIBRUJ`, wg `opis_software.md` §5) |
| 6 | Spływ | Odliczanie do końca spływu | Czeka zadany czas | Koniec → 7 |
| 7 | Rozgarnianie | „Maszyna rozgarnia próbkę” | `POMIAR` | Sukces → 8 |
| 8 | Zdjęcie | „Robię zdjęcie”; jeśli brak LED — patrz §8 | Zdjęcie, zapis do kolejki na Pi | Sukces → 9 |
| 9 | Analiza | „Analizuję…” lub „Wynik po przywróceniu łączności” | Wysyłka na serwer | Odpowiedź → 10 |
| 10 | Wynik | Wynik, napis TEST, przycisk DALEJ | — | DALEJ → 11 |
| 11 | Czyszczenie | „Maszyna czyści stół” | `PRZYGOTUJ SZCZELINA=0.5`, potem `POMIAR`; zdejmuje znacznik brudnego stołu | Sukces → 12 lub 3 |
| 12 | Opróżnij pudełko | „Wyjmij i opróżnij pudełko na kamyki”, przycisk OPRÓŻNIONE | Co `oproznianie_co_n` pomiarów, licznik na dysku | Potwierdzenie → 3 |
| — | Błąd | Treść błędu po polsku, przycisk Odblokuj | `ODBLOKUJ` | → 2 |

Pracownik widzi słowa z kolumny „Co widzi”, nigdy nazwy makr.

**Brudny stół:** znacznik zapisany na dysku jest ustawiany przed pierwszym ruchem cyklu, tj. przed
ekranem 4, a zdejmowany po udanym czyszczeniu. Przeżywa restart i zanik prądu. Gdy jest ustawiony,
po kalibracji aplikacja przechodzi prosto na ekran 11 zamiast 3. Anuluj, STOP, błąd makra i
1 h bezczynności nie wymagają więc osobnych przejść.

**Licznik opróżniania** liczy czyszczenia, także te wymuszone, bo każde zsypuje kamyki do pudełka.

**Serwer niedostępny na ekranie 9:** zdjęcie zostaje w kolejce, a pasek stanu pokazuje liczbę
oczekujących. Robotnik może przejść dalej i czyścić stół; wynik pojawia się na liście ostatnich
wyników po przywróceniu łączności.

**Pełna kolejka:** ekran Gotowa blokuje NOWY POMIAR z komunikatem „Kolejka pełna — powiadom serwis”.
Zdjęcia w kolejce nie są nadpisywane.

**Tryb serwisowy:** chroniony przytrzymaniem przycisku przez 5 s, jak E-07 w `spec-operacyjny.md`.
Zawiera `GORA_5MM`, `DOL_5MM`, `GORA_1MM`, `DOL_1MM`, `STAN_SYSTEMU`, ustawienia z §7 i podgląd
kamery. Ruch ręczny kasuje `przygotowany`, więc po wyjściu aplikacja wraca do Gotowa.

## 5. Sterowanie maszyną

Zasady z `docs/opis_software.md` obowiązują bez wyjątków:

- Dozwolone są wyłącznie `KALIBRUJ`, `PRZYGOTUJ`, `POMIAR`, `GORA_*`, `DOL_*`, `STAN_SYSTEMU`,
  `ODBLOKUJ` oraz `printer.emergency_stop` i `printer.firmware_restart`. Klient Moonrakera
  odrzuca wszystko inne już po swojej stronie, w tym `MANUAL_STEPPER` i makra z prefiksem `_`.
- Klipper ustawia komendy w kolejce, więc aplikacja sama blokuje kolejne wywołania, dopóki
  poprzednie trwa.
- Stan ekranu wynika ze stanu maszyny (§5 `opis_software.md`): subskrypcja `STAN_SYSTEMU` i
  `webhooks`, nie sama pamięć aplikacji. Po przeładowaniu ekran ma wrócić do właściwego kroku.
- Wymóg kalibracji po restarcie wynika z `skalibrowany = 0`, które Klipper kasuje przy restarcie.
  Aplikacja nie przechowuje własnej flagi kalibracji i nie ma ścieżki omijającej ekran 2.
- STOP wywołuje `printer.emergency_stop`. Powrót tylko przez ekran Zatrzymana, nigdy automatycznie:
  `printer.firmware_restart`, potem obowiązkowo `KALIBRUJ`. Ekran 2 po wznowieniu też wymaga naciśnięcia,
  a kalibracja nie startuje sama. Inne wyłączenia Klippera idą tą samą drogą, z dopisanym
  `state_message`.
- Błędy mapowane są według `opis_software.md` §7.

**Czyszczenie** korzysta z istniejących makr. `SZCZELINA=0.5` jest podana jawnie, żeby zgarnąć
też drobne kamyki niezależnie od szczeliny pomiarowej. Po `POMIAR` stół jest na T = 177, a
spychacz na s = 0. Czas szacunkowy to ok. 1,5 min. Sekwencja nie była sprawdzona na sprzęcie.

**Spychacz kończy na s = 405**, czyli czołem na y ≈ 477,7, nad otworem kieszeni y = 445…485.

## 6. Architektura

```
Raspberry Pi (bez Dockera)                         Serwer z GPU (Docker)
[UI React] <-> [FastAPI stacji] --HTTP REST-->     [FastAPI serwisu] -> [Analizator]
                  |      |                                               atrapa / model
                  |      +-- kolejka na dysku (zdjęcie + metadane)
                  |      +-- silnik zdjęć z acquisition/
                  +-- Moonraker :7125 -> Klipper -> SKR
```

- **`station/`** — backend FastAPI i UI React + Vite, jak `acquisition/`. Nazwy katalogów zgodne
  z `README.md`. Istniejące narzędzie `acquisition/` pozostaje bez zmian funkcjonalnych.
- **Zdjęcia** powstają silnikiem z `acquisition/` (`captureSample.py` przez `server/engine.py`):
  ten sam kontrakt, PNG + DNG i metadane. Niedozwolona jest druga implementacja budowania komendy
  kamery. Błąd kontraktu to ekran błędu, a nie wysłanie zdjęcia.
- **`service/`** — FastAPI w Dockerze. Odpowiada za przyjęcie zdjęcia i analizę, a nie za całość
  z `spec-operacyjny.md` §5.6.

**Trzy wymienne elementy**, sterowane konfiguracją, z tym samym interfejsem dla atrapy i prawdziwego:

| Element | Atrapa | Prawdziwy |
|---|---|---|
| Maszyna | Symulator z makrami, flagami i czasami, opcjonalnie skrócony | Moonraker przez WebSocket |
| Kamera | `GRAINCONTROL_DUMMY=1` z `acquisition/` | `rpicam-still` |
| Analizator | Losowy, powtarzalny wynik (§7) | Model z repo `kamyki`, w przyszłości |

Symulator maszyny musi umieć: restart z wyzerowaniem flag, zgłoszenie błędu w każdym makrze i
utratę połączenia.

## 7. API i kolejka

`POST /api/v1/pomiary` (multipart): PNG i metadane (`id_pomiaru` jako UUID, `numer_probki`,
`kod_partii` lub null, `id_stacji`, `czas_zdjecia`, metadane akwizycji).

```json
{
  "id_pomiaru": "…",
  "werdykt": "akceptowalna | nieakceptowalna",
  "liczba_kamieni": 1234,
  "liczba_wtracen": 25,
  "udzial_wtracen_proc": 2.0,
  "zrodlo_wyniku": "atrapa | model",
  "wersja_analizatora": "atrapa-1"
}
```

- Ponowne wysłanie tego samego `id_pomiaru` zwraca poprzedni wynik (idempotencja, US-017).
- Odpowiedź przy `zrodlo_wyniku = "atrapa"` powoduje wyświetlenie „TEST – wynik niemiarodajny”.
  Decyduje o tym odpowiedź serwera, a nie ustawienie ekranu.
- Atrapa liczy wynik deterministycznie z `id_pomiaru` i czeka konfigurowalny czas
  (domyślnie 10 s). Można wymusić wynik lub błąd zmienną środowiskową, do testów.
- Zdjęcie jest zapisywane na serwerze w woluminie Dockera.

**Kolejka na Pi:** zdjęcie i metadane trafiają na dysk przed pierwszą próbą wysyłki, wysyłane są w
kolejności FIFO z ponawianiem, a usuwane dopiero po potwierdzeniu serwera. Limit kolejki jest
konfigurowalny. Kolejka i wyniki przeżywają restart.

**Numeracja:** licznik zapisany atomowo na dysku, zwiększany co 1, zaczyna od 1, przeżywa restart i
nie wraca do użytych numerów, także po anulowaniu (por. commit 4d4cbe0). Reset tylko w trybie
serwisowym, z potwierdzeniem.

**Skanowanie:** czytnik USB w trybie klawiatury. `skanowanie_wlaczone` domyślnie `false`. Po
włączeniu ekran 3 wymaga kodu, a numer próbki nadal się nalicza. Walidacja formatu z BR-010.

**Ustawienia:** plik JSON na Pi, edytowalny z trybu serwisowego:
`skanowanie_wlaczone`, `czas_splywu_s`, `szczelina_mm`, `adres_serwisu`, `adres_moonrakera`,
`id_stacji`, `limit_kolejki`, `oproznianie_co_n` (domyślnie 1). `czas_splywu_s` ma domyślnie 30 s i wymaga ustalenia na sprzęcie.
Gdy `szczelina_mm` jest puste, `PRZYGOTUJ` idzie bez parametru. Wartość z makra to 0,5 mm i wymaga
ustawienia przed testami z materiałem: przy ziarnie ok. 1,9 mm zgarnęłaby praktycznie wszystko.

## 8. Założenia i wybory projektanta

Nie uzgodnione wprost, do sprawdzenia przy czytaniu:

- **LED** świeci przez całą pracę. Ekran 8 tylko przypomina o nim tekstem.
- **Raspberry Pi bez Dockera**, ze względu na bezpośredni dostęp do kamery.
- **Docker ma dwa warianty** w `service/Dockerfile`: `mock` bez PyTorcha, do pracy na każdym
  komputerze, oraz `gpu` z PyTorch + CUDA, który przy starcie raportuje GPU w `/health`.
  `docker-compose.yml` wybiera wariant profilem. Analizator w obu to na razie atrapa.
- **Brak uwierzytelniania** w sieci testowej, czego nie wolno przenieść na produkcję (NFR-005).
- **Komunikacja UI z backendem** — dowolna (WebSocket lub polling), ważne, żeby stan był zawsze
  zgodny z backendem.
- **Powrót po restarcie:** backend zapisuje dziennik cyklu na dysku (bieżący krok, numer próbki,
  `id_pomiaru`), bo flagi maszyny nie rozróżniają kroków. Po przeładowaniu przeglądarki ekran wraca
  do stanu z backendu. Po restarcie backendu lub Pi aplikacja wznawia cykl według dziennika, a
  czekając na koniec makra, nie wywołuje `ODBLOKUJ`. Jeśli stan maszyny nie pasuje do dziennika,
  uznaje cykl za przerwany.
- **Błąd zdjęcia na ekranie 8:** osobny komunikat i przycisk „Ponów zdjęcie”, bez `ODBLOKUJ` i bez
  kalibracji, bo maszyna jest sprawna, a próbka leży rozgarnięta. Bez limitu prób. Odniesieniem
  macierzy CCM jest pierwsze udane ujęcie od startu aplikacji; reset odniesienia w trybie serwisowym.
- **Serwer odrzuca zdjęcie (400, 422):** zdjęcie trafia do osobnego katalogu „odrzucone”, nie blokuje
  kolejki i nie wlicza się do limitu, a robotnik widzi „Błąd analizy — powiadom serwis”.
  **Każda inna odpowiedź bez poprawnego wyniku tego pomiaru albo brak odpowiedzi w 60 s** to „serwer
  niedostępny”: ponawianie z odstępem, zdjęcie zostaje.
- **Nieudany STOP** (maszyna nieosiągalna): czerwony komunikat „odłącz zasilanie maszyny” i ponawianie
  do skutku. Każdy STOP, także poza cyklem, wymusza po kalibracji czyszczenie.
- **Prawdziwa maszyna z atrapą kamery nie startuje** bez jawnego `STACJA_ATRAPA_KAMERY=1`, a domyślnym
  trybem stacji nie jest symulator.
- **DNG jest wysyłany razem z PNG** jako opcjonalne pole `raw`, a kopia lokalna znika po
  potwierdzeniu zapisu. `rekomendacja.md` §5 uznaje RAW za warunek odwracalności badań, a stacja nie
  jest archiwum (BR-009).
- **Rozmiar celów dotykowych** min. 12 × 12 mm (NFR-009), główny przycisk zdecydowanie większy.
  Ciemny motyw i paleta z `acquisition/web/src/styles.css`. Język polski.

## 9. Testy

- Testy backendu stacji na symulatorze maszyny: pełny przebieg, restart wymuszający kalibrację,
  STOP w każdym kroku, błąd makra na każdym kroku, odrzucanie makr spoza listy.
- Testy brudnego stołu i pudełka: przerwanie na każdym kroku wymusza czyszczenie, także po restarcie;
  blokada co N pomiarów.
- Test, że żaden ruch nie startuje po STOP bez przytrzymania „Wznów” i naciśnięcia kalibracji.
- Testy kolejki: serwer niedostępny, restart w trakcie, ponowienie bez duplikatu, pełna kolejka.
- Testy licznika: restart, anulowanie, brak powtórzeń.
- Test kontraktowy API serwisu i kontrola, że wynik atrapy zawsze pokazuje TEST.
- Przejście całego przebiegu w przeglądarce w rozmiarze 1280 × 800.
- `docker compose up` w wariancie `mock` i wysłanie zdjęcia do działającego kontenera.
- Wariant `gpu`: budowa i raport GPU tam, gdzie jest dostępny NVIDIA Container Toolkit.

## 10. Co trzeba potwierdzić na sprzęcie

Nie blokuje budowy, ale blokuje realne użycie:

- Działanie `docs/printer.cfg`, zwłaszcza pole `manual_stepper … position` i bazowanie StallGuard.
- Czasy makr, czas spływu, sekwencja czyszczenia.
- Szczelina pomiarowa (§7).
- Kadr jednej kamery przy T = 177 ok. 295 × 221 mm, czyli ok. 72% pola 300 × 300 mm.
- Nowy profil akwizycji: P2 dotyczy innej odległości i ogniskowej (`WYMIANA-KAMERY.md`). Bez
  nowego profilu zdjęcia z maszyny nie są porównywalne ze zdjęciami z badań.
- Czas prawdziwej analizy: ok. 24 s zmierzone, 10 s wymagane przez NFR-001.
