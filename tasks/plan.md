# Plan: UI stanowiska „Kostka mati”

Źródła: `SPEC.md`, `docs/superpowers/specs/2026-11-05-ui-stanowiska-design.md` (Projekt).
Lista postępu: `tasks/todo.md`.

## Decyzje architektoniczne

- **Sercem jest `Cykl` w backendzie:** automat stanów z dziennikiem na dysku. UI tylko pokazuje stan i wysyła zdarzenia, dzięki czemu
  przeładowanie przeglądarki nic nie psuje.
- **Maszyna za interfejsem `Maszyna`:** `SymulatorMaszyny` i `MoonrakerMaszyna`. Lista makr jest pilnowana w jednym miejscu, przed każdą implementacją.
- **Zdjęcia przez `CaptureController`** z `acquisition/server` (`PYTHONPATH=acquisition:station`).
- **UI łączy się przez polling `GET /api/stan`** co 300 ms: proste i odporne na zerwania.
- **Sterowanie testami:** `/api/dev/*` tylko przy symulatorze; czas przyspieszany `STACJA_TEMPO`.
- **Kolejka na dysku:** katalog na pomiar, zapis atomowy, wątek wysyłki FIFO.

## Zależności

```
T1 szkielet+kalibracja → T2 cykl do POMIAR → T3 zdjęcie ─┐
T4 serwis+atrapa+Docker mock ────────────────────────────┴→ T5 wysyłka+wynik → T6 awarie serwera
T5 → T7 czyszczenie+pudełko+brudny stół → T8 STOP+błędy → T9 odtwarzanie po restarcie
T7 → T10 tryb serwisowy+skanowanie;  T1 → T11 Moonraker;  T4 → T12 Docker GPU;  wszystko → T13 odbiór
```

## Definicja ukończenia zadania

pytest i Playwright zielone (cały zestaw, nie tylko nowe testy), zbudowane UI, commit lokalny. Bez pusha.
Każdy nowy tekst ekranu po polsku, bez nazw makr, bez przewijania w 1280 × 800.

## Faza 1: przebieg na maszynie

### T1: Szkielet i obowiązkowa kalibracja (M)
Backend, symulator, ekrany Brak połączenia, Kalibracja, Gotowa, `run-dev.sh`, konfiguracja Playwrighta.
- Świeży start i restart symulatora prowadzą na Kalibrację; nie ma ścieżki omijającej.
- Kalibracja startuje dopiero po naciśnięciu przycisku.
- Makro spoza listy jest odrzucane przed wysłaniem.
- Playwright: start → Kalibruj → Gotowa; restart symulatora → znów Kalibracja; utrata połączenia → Brak połączenia.

### T2: Cykl do rozgarnięcia i numeracja (M)
Ekrany 3–7, trwały licznik próbek.
- Przejście Nowy pomiar → Przygotowanie → Wsyp → Spływ → Rozgarnianie, z wywołaniem właściwych makr.
- Anuluj wraca do kalibracji; numer nie wraca do obiegu; licznik przeżywa restart.
- Playwright: cykl i numer rosnący o 1; test braku przewijania.

### T3: Zdjęcie (S)
Ekran 8 przez `CaptureController` w trybie atrapy; błąd z przyciskiem Ponów, bez `ODBLOKUJ`.
- Zdjęcie trafia do kolejki na dysk (PNG, DNG, metadane) przed wysyłką.
- Błąd lub odrzucenie przez kontrakt pokazuje Ponów; ponowienie działa bez kalibracji.
- Playwright: sukces i awaria wymuszona przez `/api/dev`.

### Punkt kontrolny A
Pełny przebieg do zdjęcia działa; testy zielone.

## Faza 2: serwer i wynik

### T4: Serwis z atrapą i Docker `mock` (M)
`service/`: API wg Projektu §7, idempotencja, deterministyczna atrapa, zapis pliku, `/health`, Dockerfile, compose.
- `zrodlo_wyniku = "atrapa"` zawsze przy atrapie; to samo `id_pomiaru` daje ten sam wynik, bez duplikatu.
- `docker compose --profile mock up` przyjmuje zdjęcie, jeśli Docker jest dostępny.
- Playwright: test API `/health` i wysyłki (`request`).

### T5: Wysyłka i ekran wyniku (M)
Uploader FIFO, ekrany 9–10, `run-dev.sh` uruchamia też serwis.
- Ekran Analizuję, potem wynik.
- Napis TEST wynika z odpowiedzi serwera.
- Plik lokalny znika dopiero po potwierdzeniu.
- Playwright: cały cykl aż do wyniku z napisem TEST.

### T6: Awarie serwera (S)
Niedostępny serwer, 4xx, pełna kolejka, lista ostatnich wyników.
- Brak serwera: komunikat, praca dalej, po powrocie wysyłka bez duplikatu.
- 4xx: katalog `odrzucone`, kolejka idzie dalej, komunikat o serwisie.
- Pełna kolejka blokuje Nowy pomiar.
- Playwright: wyłączenie i przywrócenie serwera.

### Punkt kontrolny B
Cykl do wyniku działa także przy przerwie w łączności.

## Faza 3: bezpieczeństwo i odporność

### T7: Czyszczenie, pudełko, brudny stół (M)
Ekrany 11–12, trwały znacznik i licznik.
- Po wyniku idzie `PRZYGOTUJ SZCZELINA=0.5` i `POMIAR`, potem pudełko co N czyszczeń.
- Znacznik ustawiany przed pierwszym ruchem cyklu; po kalibracji z brudnym stołem idzie od razu czyszczenie.
- Playwright: pełny cykl; Anuluj → kalibracja → czyszczenie → pudełko.

### T8: STOP i błędy makr (M)
STOP na każdym ekranie, ekran Zatrzymana z przytrzymaniem 3 s, ekran Błąd z mapowaniem z `opis_software.md` §7.
- Po STOP żadnego ruchu bez przytrzymania i naciśnięcia kalibracji; krótsze przytrzymanie nic nie robi.
- Błąd makra → Błąd → Odblokuj → Kalibracja → czyszczenie.
- Playwright: STOP w trakcie ruchu i wznowienie; wymuszony błąd.

### T9: Odtwarzanie po restarcie backendu (M)
Dziennik cyklu, bezpieczne wznawianie.
- Restart w każdym kroku prowadzi do stanu zgodnego z Projektem §8, bez `ODBLOKUJ` w trakcie działającego makra.
- Stan maszyny niezgodny z dziennikiem → cykl przerwany, wymuszone czyszczenie.
- Wynik sprzed restartu nadal widoczny.
- Playwright: restart procesu backendu w trakcie cyklu.

### Punkt kontrolny C
Kryteria sukcesu 1–9 ze SPEC przechodzą.

## Faza 4: domknięcie

### T10: Tryb serwisowy i skanowanie (M)
Wejście przez przytrzymanie 5 s, ruchy ręczne, ustawienia, reset licznika; skanowanie domyślnie wyłączone.
- Po włączeniu skanowania Nowy pomiar wymaga poprawnego kodu; kod trafia do metadanych.
- Ruch ręczny kasuje gotowość; po wyjściu aplikacja wraca do Gotowa.
- Playwright: wejście, ruch, przełącznik, skan z klawiatury.

### T11: Klient Moonrakera (M)
`MoonrakerMaszyna`, testowany na lokalnej atrapie WebSocket zgodnej z `opis_software.md`.
- `printer.gcode.script`, subskrypcja, `notify_status_update`, błąd makra, rozłączenie i ponowne połączenie.
- Cała logika cyklu działa z nim bez zmian, wybór przez konfigurację.
- Playwright: przebieg kalibracji ze stacją połączoną przez atrapę WebSocket.

### T12: Docker GPU i dokumentacja (S)
Wariant `gpu`, `/health` z raportem GPU, `station/README.md`, `service/README.md`.
- Budowa i raport GPU sprawdzone, o ile środowisko pozwala; inaczej odnotowane jako niesprawdzone.
- Playwright: regresja całego zestawu.

### T13: Odbiór (S)
Przejście kryteriów SPEC, zrzuty każdego ekranu w 1280 × 800, pełny bieg testów, przegląd kodu niezależnym agentem i poprawki.

## Ryzyka

| Ryzyko | Wpływ | Działanie |
|---|---|---|
| Moonraker działa inaczej niż atrapa | Wysoki | Atrapa wg dokumentacji; próba na sprzęcie w osobnym kroku, jawnie niesprawdzone |
| `printer.cfg` nietestowany | Wysoki | Aplikacja nie zależy od szczegółów ruchu; lista w Projekcie §10 |
| Docker bez GPU w WSL | Średni | Wariant `mock` niezależny od GPU; `gpu` raportuje brak zamiast się wywracać |
| Niestabilne testy czasowe | Średni | `STACJA_TEMPO`, oczekiwanie na stan zamiast opóźnień |
| Python 3.13 lokalnie, inna wersja na Pi | Niski | Kod zgodny z 3.11, bez nowszych funkcji |
