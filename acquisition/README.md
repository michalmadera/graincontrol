# acquisition — warstwa 1

Program stanowiska fotograficznego. Wykonuje zdjęcie na **zamrożonych** parametrach
(czas naświetlania, wzmocnienie, balans bieli, parametry ISP) i zapisuje je razem
z metadanymi akwizycji.

Zasada nadrzędna: program ma **uniemożliwić** zebranie danych, których później nie da się
porównać. Kontrakt akwizycji sprawdzany jest po każdym ujęciu, nie raz na sesję.

Produkt warstwy: archiwum zdjęć PNG (bezstratnych, w pełnej rozdzielczości) o wspólnym
`akwizycja_profil_id`, które da się połączyć w jeden zbiór i przepuścić przez `measurement/`.

Specyfikacja: [../docs/spec-akwizycji.md](../docs/spec-akwizycji.md)
Stan strojenia toru optycznego: [../docs/rekomendacja.md](../docs/rekomendacja.md)
Procedura przy stanowisku: [../docs/spec-przygotowanie-materialu.md](../docs/spec-przygotowanie-materialu.md)
