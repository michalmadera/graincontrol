# Postęp: UI stanowiska „Kostka mati”

Plan: `tasks/plan.md`. Każde zadanie: pytest + Playwright na atrapach, commit lokalny, bez pusha.

## Faza 1: przebieg na maszynie
- [x] T1 Szkielet i obowiązkowa kalibracja
- [x] T2 Cykl do rozgarnięcia i numeracja
- [x] T3 Zdjęcie
- [x] Punkt kontrolny A

## Faza 2: serwer i wynik
- [x] T4 Serwis z atrapą i Docker `mock`
- [x] T5 Wysyłka i ekran wyniku
- [x] T6 Awarie serwera
- [x] Punkt kontrolny B

## Faza 3: bezpieczeństwo i odporność
- [x] T7 Czyszczenie, pudełko, brudny stół
- [x] T8 STOP i błędy makr
- [x] T9 Odtwarzanie po restarcie backendu
- [x] Punkt kontrolny C

## Faza 4: domknięcie
- [x] T10 Tryb serwisowy i skanowanie
- [x] T11 Klient Moonrakera
- [x] T12 Docker GPU i dokumentacja
- [x] T13 Odbiór

## Notatki
- Niezależny przegląd kodu znalazł 18 usterek; poprawione, z testami w `station/tests/test_przeglad.py` i `web/e2e/t13-odbior.spec.js`.
- Niesprawdzone: prawdziwy Moonraker, `printer.cfg`, kamera, wykrycie GPU w kontenerze (Docker na tym komputerze nie uruchamia kontenerów z GPU).
- Znane ograniczenie: ekran pokazuje 5 ostatnich wyników, starsze są zapisane na stacji, ale niewidoczne.
- Po 1 h bezczynności na ekranie wyniku pojawia się kalibracja; wynik zostaje na liście ostatnich.
