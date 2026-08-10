# profiles — profile akwizycji i profile oceny

Wersjonowane pliki konfiguracyjne, wytwarzane przez tor badawczy i konsumowane przez tor
operacyjny.

```
profiles/
├── acquisition/   profile akwizycji (parametry zamrożone dla stanowiska)
└── assessment/    profile oceny (progi, klasy wtrąceń, warunki ważności)
```

Reguły:

- Profile **nie są nadpisywane ani usuwane** — nowy plik to nowy `profil_id`.
- Przy wczytaniu liczona jest suma SHA-256 i zapisywana przy każdym pomiarze ocenionym
  tym profilem.
- Zbiór klas wtrąceń pochodzi wyłącznie z profilu oceny i jest wspólny z listą przyczyn
  odrzucenia używaną przy etykietowaniu materiału w torze badawczym (BR-015). Rozjechanie
  się obu słowników unieważnia materiał uczący.

Schemat pliku: [../docs/spec-operacyjny.md](../docs/spec-operacyjny.md) §6.1
