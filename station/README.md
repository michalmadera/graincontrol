# station — aplikacja stacji pomiarowej

Aplikacja na Raspberry Pi z kamerą i ekranem dotykowym, pracująca w trybie kiosk.
Rejestracja dostawy, wyzwolenie pomiaru, prezentacja werdyktu, prowadzenie operatora przez
procedurę próbek kontrolnych (2 z 3) oraz buforowanie offline.

Stacja nie zawiera logiki oceny — próg, werdykt i status dostawy wyznacza [../service/](../service/).
Stacja nie jest archiwum: lokalną kopię zdjęcia usuwa po potwierdzeniu zapisu (BR-009).

Katalog ekranów (E-01…E-07) i wymagania: [../docs/spec-operacyjny.md](../docs/spec-operacyjny.md) §5.1–5.5
