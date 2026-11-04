# Kostka mati – interfejs sterowania maszyną dla aplikacji webowej

Dokument dla programisty aplikacji (UI na ekranie dotykowym Raspberry Pi). Opisuje, jak wywoływać makra maszyny, jakie dane obserwować i jak przełożyć je na stany ekranu. Szczegóły mechaniki i dokładne ruchy osi: `docs/architecture_baseline.md` (sekcje 4–5) – do napisania interfejsu nie są potrzebne.

> Status: konfiguracja Klippera (`klipper/printer.cfg`) nie była jeszcze uruchomiona na maszynie. Nazwy makr i zmiennych są ustalone, ale zachowanie (czasy, komunikaty Klippera) trzeba potwierdzić na żywo.

---

## 1. Architektura w skrócie

```
[Aplikacja webowa / UI]  --HTTP lub WebSocket (JSON-RPC)-->  [Moonraker :7125]  -->  [Klipper]  -->  [płytka SKR, silniki]
         |
         +-- kamery (obsługiwane bezpośrednio przez aplikację, nie przez Klippera)
```

- Maszyna ma dwie osie: **stół** (góra/dół) i **spychacz** (rozgarnia kamyki po stole). Aplikacja nie steruje osiami bezpośrednio – wywołuje wyłącznie **makra** opisane w sekcji 3.
- Makra same pilnują bezpieczeństwa (kolizje, zakresy, kolejność kroków). Aplikacja nie musi tego liczyć, ale powinna blokować przyciski zgodnie z sekcją 5, żeby użytkownik nie dostawał zbędnych błędów.
- **Nie wysyłać komend `MANUAL_STEPPER` ani innych G-code poza makrami z tej listy** – omijają zabezpieczenia.
- Oświetlenie LED jest włączane ręcznie przełącznikiem – aplikacja go nie steruje (może tylko przypomnieć użytkownikowi).
- Zdjęcia robi aplikacja (kamery Raspberry Pi), po zakończeniu makra `POMIAR`.

## 2. Połączenie z Moonrakerem

Moonraker działa na Raspberry Pi, domyślnie port **7125**. Zalecany kanał: **WebSocket** `ws://<host>:7125/websocket` (JSON-RPC 2.0) – jedno połączenie do wywołań i do nasłuchu zmian.

Jeśli aplikacja jest serwowana z innego adresu niż Moonraker, trzeba dopisać jej domenę w `moonraker.conf` (`[authorization]` → `cors_domains` / `trusted_clients`).

### 2.1 Wywołanie makra

WebSocket:

```json
{"jsonrpc": "2.0", "method": "printer.gcode.script", "params": {"script": "KALIBRUJ"}, "id": 101}
```

HTTP (alternatywa):

```
POST http://<host>:7125/printer/gcode/script
Content-Type: application/json

{"script": "KALIBRUJ"}
```

Makra z parametrem opcjonalnym: `{"script": "PRZYGOTUJ SZCZELINA=1.5"}` (patrz sekcja 3 – w praktyce wywoływać bez parametrów).

**Ważne – odpowiedź przychodzi dopiero po zakończeniu makra:**

| Wynik | Co przychodzi |
|---|---|
| Sukces | `{"result": "ok", "id": 101}` |
| Błąd (makro odrzucone lub przerwane) | `{"error": {"code": 400, "message": "<treść błędu>"}, "id": 101}` |

- Makra ruchu trwają od kilku sekund do ok. 1,5–2 minut (sekcja 3). Nie ustawiać krótkiego timeoutu na żądanie; postęp pokazywać na podstawie stanu (sekcja 2.2).
- Klipper wykonuje komendy **po kolei**. Komenda wysłana w trakcie działania makra nie zostanie odrzucona – zaczeka w kolejce i wykona się po nim. Dlatego aplikacja **sama musi blokować przyciski**, dopóki trwa poprzednie wywołanie.

### 2.2 Nasłuch stanu

Po połączeniu jednorazowo zasubskrybuj obiekty:

```json
{"jsonrpc": "2.0", "method": "printer.objects.subscribe", "id": 1,
 "params": {"objects": {
   "gcode_macro STAN_SYSTEMU": ["zajety", "skalibrowany", "przygotowany"],
   "webhooks": ["state", "state_message"],
   "manual_stepper stol": ["position"],
   "manual_stepper spychacz": ["position"]
 }}}
```

- Odpowiedź zawiera stan początkowy; później zmiany przychodzą jako powiadomienia **`notify_status_update`** (tylko pola, które się zmieniły – scalać z poprzednim stanem).
- Do jednorazowego odczytu: `printer.objects.query` z tymi samymi parametrami (HTTP: `GET /printer/objects/query?gcode_macro%20STAN_SYSTEMU`).
- `manual_stepper …` – pozycje osi, potrzebne tylko do ewentualnego podglądu i metadanych zdjęć; dostępność tego obiektu w używanej wersji Klippera do potwierdzenia na żywo.

### 2.3 Inne powiadomienia do obsłużenia

| Powiadomienie | Znaczenie dla UI |
|---|---|
| `notify_gcode_response` | Komunikaty tekstowe z maszyny. Linie zaczynające się od `echo:` to informacje z makr (np. „Wsyp probke…”). Linie zaczynające się od `!!` to błędy. Wyświetlać w pasku komunikatów / logu. |
| `notify_klippy_ready` | Klipper gotowy – ponownie zasubskrybować obiekty i odczytać stan. |
| `notify_klippy_shutdown` / `notify_klippy_disconnected` | Maszyna niedostępna – ekran „brak połączenia z maszyną”. |
| `webhooks.state` ≠ `ready` | To samo – maszyna niegotowa (`startup`, `shutdown`, `error`); `state_message` zawiera opis. |

### 2.4 Zatrzymanie awaryjne

- `printer.emergency_stop` (HTTP: `POST /printer/emergency_stop`) – natychmiastowe zatrzymanie silników, Klipper przechodzi w stan `shutdown`.
- Powrót do pracy: `printer.firmware_restart` (HTTP: `POST /printer/firmware_restart`), poczekać na `notify_klippy_ready`, potem obowiązkowo `KALIBRUJ`.
- Przycisk STOP powinien być dostępny zawsze, także w trakcie trwania makra.

## 3. Makra

| Makro | Co robi | Kiedy dostępne | Czas (orientacyjnie) |
|---|---|---|---|
| `KALIBRUJ` | Bazowanie obu osi – maszyna sama ustala położenie stołu i spychacza (jazda do oporów mechanicznych), kończy w pozycji spoczynkowej: stół na dole, spychacz z tyłu. | Zawsze, gdy maszyna nie jest zajęta. Wymagane po starcie, po błędzie, po zatrzymaniu awaryjnym, po długiej bezczynności. | ok. 1,5–2 min |
| `PRZYGOTUJ` | Ustawia maszynę do wsypania próbki: spychacz odjeżdża do tyłu, stół podjeżdża maksymalnie wysoko pod lejek (najkrótszy zsyp kamyków). | Po `KALIBRUJ`. | do ok. 40 s |
| `POMIAR` | Rozgarnia wsypaną próbkę w jedną warstwę (nadmiar do kieszeni), chowa spychacz i opuszcza stół do pozycji zdjęć. Po zakończeniu aplikacja robi zdjęcia. | Tylko bezpośrednio po `PRZYGOTUJ` i wsypaniu próbki. | ok. 1 min |
| `GORA_5MM`, `DOL_5MM`, `GORA_1MM`, `DOL_1MM` | Ręczny ruch stołu w górę / w dół (krok duży i mały) – do serwisu i testów. | Po `KALIBRUJ`. Ruch niedozwolony w danej pozycji zostanie odrzucony komunikatem. Ruch ręczny anuluje gotowość z `PRZYGOTUJ`. | kilka s |
| `STAN_SYSTEMU` | Wypisuje stan maszyny w `notify_gcode_response`. Do diagnostyki – aplikacja powinna czytać stan z subskrypcji (2.2), nie z tego tekstu. | Zawsze. | natychmiast |
| `ODBLOKUJ` | Zdejmuje blokadę po błędzie. Kasuje kalibrację – po nim wymagane `KALIBRUJ`. | Gdy `zajety = 1`, a żadne makro nie jest w toku (sekcja 5). | natychmiast |

Parametry opcjonalne (w normalnej pracy **nie podawać** – wartości domyślne są ustawione w konfiguracji):
- `PRZYGOTUJ SZCZELINA=<mm>` – szczelina pod spychaczem; przyszłościowo do różnych frakcji kamyków.
- `POMIAR SPEED=<mm/s>` – prędkość rozgarniania; do strojenia.

## 4. Zmienne stanu (`gcode_macro STAN_SYSTEMU`)

| Zmienna | Wartości | Znaczenie |
|---|---|---|
| `zajety` | 0 / 1 | 1 = makro ruchu w toku **albo** poprzednie makro zostało przerwane błędem (blokada). |
| `skalibrowany` | 0 / 1 | 1 = osie zbazowane, maszyna zna swoje położenie. Kasowane po restarcie Klippera, `ODBLOKUJ` i po 1 h bezczynności (silniki są wtedy wyłączane). |
| `przygotowany` | 0 / 1 | 1 = maszyna stoi w pozycji do wsypania próbki (po `PRZYGOTUJ`). Kasowane przez `POMIAR`, ruch ręczny, `KALIBRUJ`, `ODBLOKUJ`. |

Rozróżnienie „pracuje” vs „zablokowana po błędzie” wymaga informacji z aplikacji: jeśli `zajety = 1` i aplikacja **ma** niezakończone żądanie → maszyna pracuje; jeśli `zajety = 1` i **nie ma** oczekującego żądania (np. przyszła odpowiedź z błędem albo aplikacja została przeładowana) → blokada po błędzie.

## 5. Stany ekranu (propozycja)

| Stan UI | Warunek | Aktywne akcje |
|---|---|---|
| **Brak połączenia** | brak WebSocket lub `webhooks.state` ≠ `ready` | – (ewentualnie `printer.firmware_restart` w trybie serwisowym) |
| **Pracuje** | aplikacja czeka na odpowiedź makra | tylko STOP |
| **Błąd / blokada** | `zajety = 1` i brak oczekującego żądania | `ODBLOKUJ` (+ STOP) |
| **Wymaga kalibracji** | `skalibrowany = 0` | `KALIBRUJ` |
| **Gotowa** | `skalibrowany = 1`, `przygotowany = 0` | `PRZYGOTUJ` (start pomiaru), `KALIBRUJ`, ruchy ręczne (tryb serwisowy) |
| **Czeka na próbkę** | `przygotowany = 1` | komunikat „Wsyp próbkę do lejka”, przycisk „Próbka wsypana” → odczekanie na spływ → `POMIAR`; przycisk „Anuluj” (np. `KALIBRUJ`) |
| **Zdjęcia** | `POMIAR` zakończony sukcesem | przypomnienie o LED, wykonanie zdjęć, zapis; potem powrót do „Gotowa” |

Stan STOP dostępny zawsze.

## 6. Typowy przebieg pomiaru

```
start aplikacji
  └─ subskrypcja stanu (2.2)
  └─ skalibrowany = 0?  →  KALIBRUJ
PRZYGOTUJ
  └─ UI: „Wsyp próbkę do lejka” → użytkownik potwierdza
  └─ odczekanie na spływ kamyków przez rozprowadzacz (czas do ustalenia doświadczalnie – parametr w ustawieniach aplikacji)
POMIAR
  └─ odpowiedź "ok"
  └─ UI: przypomnienie o włączeniu LED (przełącznik) – opcjonalnie potwierdzenie
  └─ zdjęcia z obu kamer + zapis metadanych
  └─ powrót do stanu „Gotowa” (kolejny pomiar zaczyna się od PRZYGOTUJ)
```

Metadane do zapisania przy zdjęciach: znacznik czasu, frakcja / opis próbki (z UI), wysokość stołu (`manual_stepper stol.position`), szczelina rozgarniania (domyślna lub podana w `PRZYGOTUJ`). Przeliczenie wysokości stołu na odległość kamera–płyta: `docs/architecture_baseline.md`.

Kieszeń z nadmiarem kamyków opróżnia użytkownik ręcznie – warto dodać licznik pomiarów / przypomnienie.

## 7. Obsługa błędów

Błąd przychodzi jako odpowiedź `error` na wywołanie makra oraz jako linia `!! …` w `notify_gcode_response`. Treść zaczyna się nazwą makra lub osi – wystarczy pokazać ją użytkownikowi i dobrać akcję:

| Fragment komunikatu | Przyczyna | Zachowanie UI | Blokada? |
|---|---|---|---|
| `system zajety` | Wywołano makro, gdy blokada jest aktywna | Pokazać ekran „Błąd / blokada” | – |
| `osie nieskalibrowane` | Brak kalibracji | Zaproponować `KALIBRUJ` | nie |
| `najpierw PRZYGOTUJ` | `POMIAR` bez `PRZYGOTUJ` | Wrócić do kroku `PRZYGOTUJ` | nie |
| `odrzucono` | Ruch ręczny niedozwolony w tej pozycji | Komunikat, nic więcej | nie |
| `SZCZELINA … <` / `za duza` | Zły parametr `PRZYGOTUJ` | Komunikat | nie |
| `INTERLOCK`, `poza zakresem` w trakcie makra cyklu | Zabezpieczenie zatrzymało ruch (nie powinno wystąpić w normalnej pracy) | Ekran błędu, `ODBLOKUJ` → `KALIBRUJ` | **tak** |
| Błąd Klippera w trakcie `KALIBRUJ` (brak wykrycia oporu przy bazowaniu) | Kalibracja nieudana – do sprawdzenia mechanika / ustawienia | Ekran błędu, `ODBLOKUJ` → ponowne `KALIBRUJ`; przy powtórzeniu – serwis | **tak** |

Zasada ogólna: jeśli po błędzie `zajety = 1`, maszyna jest zablokowana i jedyna droga dalej to `ODBLOKUJ` → `KALIBRUJ`.

Dodatkowo po 1 h bezczynności maszyna sama wyłącza silniki (komunikat `echo: Bezczynnosc…`, `skalibrowany` → 0) – UI przechodzi do stanu „Wymaga kalibracji”.

## 8. Do potwierdzenia na żywo

- Rzeczywiste czasy trwania makr (do paska postępu / timeoutów).
- Dokładna treść błędów Klippera przy nieudanej kalibracji.
- Dostępność obiektu `manual_stepper <nazwa>` w `printer.objects.subscribe` (pozycje osi).
- Czas spływu próbki przez rozprowadzacz (parametr aplikacji).
