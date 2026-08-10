# libs — kod wspólny

Rzeczy, które muszą być identyczne po obu stronach granicy między torami:

- schematy JSON profilu akwizycji i profilu oceny wraz z walidacją,
- identyfikatory ziarna, próbki i pomiaru oraz format rekordu wyniku,
- definicje klas wtrąceń (odczyt z profilu, bez wartości domyślnych),
- klient REST API serwisu, używany przez stację i przez narzędzia toru badawczego,
- liczenie sumy kontrolnej profilu.

Zasada: brak wymaganego pola w profilu jest błędem, nie wartością domyślną. Wartości
domyślne w bibliotece wspólnej to najkrótsza droga do progu, który znaczy co innego
w torze badawczym niż w produkcji.
