# panel — panel laboratorium

Aplikacja przeglądarkowa dla laboratorium i administracji: przegląd dostaw i pomiarów,
kolejka dostaw oczekujących na decyzję, podgląd zdjęć z warstwą wykrytych wtrąceń,
rejestracja decyzji przyjęcie/odrzucenie, adnotacje zdjęć, eksport CSV oraz wczytywanie
profili oceny.

Decyzja laboratorium jest niezmienialna i nieusuwalna (BR-007). Adnotacje nie zmieniają
werdyktu ani statusu dostawy — są materiałem do dotrenowania modelu (BR-006).

Progów nie edytuje się w formularzu: administrator wczytuje nowy plik profilu, żeby wartość
obowiązująca w systemie zawsze odpowiadała plikowi o znanej sumie kontrolnej (US-030).

Specyfikacja: [../docs/spec-operacyjny.md](../docs/spec-operacyjny.md) §5.7–5.8
