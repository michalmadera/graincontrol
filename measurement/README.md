# measurement — warstwa 2

Warstwa pomiarowa: zdjęcie → maski pojedynczych ziaren → wartości liczbowe na ziarno
i na próbkę. Barwa i kształt liczone są z **tych samych masek, w tym samym przebiegu,
do tej samej tabeli**.

Warstwa nie zna progów i nie wydaje werdyktu OK/NOK. Zwraca wyłącznie liczby, na których
warstwa 3 wyznacza progi.

Wersja pipeline'u i model masek są częścią wyniku — ich zmiana przesuwa metryki
o wielokrotność rozrzutu populacji, więc unieważnia progi wyznaczone na poprzedniej wersji
(warunki ważności profilu, BR-014).

Specyfikacje: [../docs/spec-analizy-barwy.md](../docs/spec-analizy-barwy.md),
[../docs/spec-analizy-ksztaltu.md](../docs/spec-analizy-ksztaltu.md)

Prototyp poza repozytorium: `rpi_cam/analiza3/` (`measure.py`, `segment_cellpose.py`,
`spec_common.py`) — do przeniesienia tutaj.
