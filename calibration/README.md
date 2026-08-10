# calibration — warstwa 3

Wyznaczanie progów akceptacji z rozkładów zebranych na wielu próbkach. Produktem jest
**plik profilu oceny** (JSON) zapisywany do [../profiles/](../profiles/).

Profil niesie: wzorzec barwy, reguły klasyfikacji ziarna do klasy wtrącenia, progi próbki
(minimalna liczność, maksymalny udział wtrąceń ogółem i per klasa), warunki ważności oraz
ślad kalibracji (liczność zbiorów, σ_layout, FPR/FNR).

Sekcja `pochodzenie` nie bierze udziału w obliczeniach, ale jest wymagana: bez niej nie da
się później stwierdzić, na jakim materiale i z jaką skutecznością próg powstał.

Struktura pliku: [../docs/spec-operacyjny.md](../docs/spec-operacyjny.md) §6.1
