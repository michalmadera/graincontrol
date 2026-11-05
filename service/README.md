# service — serwis analizujący

Usługa na serwerze z GPU. Przyjmuje zdjęcie z metadanymi przez REST API i zwraca wynik.

**Stan:** analizator to atrapa. Wynik jest wyliczany z identyfikatora pomiaru, bez patrzenia na
zdjęcie, i zawsze ma `"zrodlo_wyniku": "atrapa"`. Stacja pokazuje wtedy napis „TEST – wynik
niemiarodajny”. Nie nadaje się do oceny materiału.

Pozostały zakres z [../docs/spec-operacyjny.md](../docs/spec-operacyjny.md) §5.6 (baza dostaw, reguła
2 z 3, profile oceny) nie jest jeszcze zrobiony.

## Uruchomienie

```bash
# Wariant lekki, działa na każdym komputerze
docker compose --profile mock up --build

# Wariant z PyTorch + CUDA, wymaga NVIDIA Container Toolkit
docker compose --profile gpu up --build
```

Port ustawia `ANALIZA_PORT` (domyślnie 8000), a czas odpowiedzi atrapy `ANALIZA_OPOZNIENIE_S`
(domyślnie 10 s). Zdjęcia trafiają do woluminu `dane`.

Sprawdzenie: `curl http://localhost:8000/health`. W wariancie `gpu` pole `gpu.dostepne` mówi, czy
kontener widzi kartę.

**Co sprawdzono (2026-11-05):** wariant `mock` działa w kontenerze i przyjmuje zdjęcie. Wariant `gpu`
buduje się (obraz ok. 8,6 GB, PyTorch 2.6.0 + CUDA 12.4), a bez dostępu do karty poprawnie zgłasza
`dostepne: false`. **Wykrycie karty w kontenerze nie zostało sprawdzone:** na komputerze
deweloperskim kontenery z `--gpus all` nie startują (`nvidia-cdi-hook: no such file or directory`),
także zwykły `python:3.11-slim`, więc to konfiguracja tamtego Dockera, a nie tego obrazu. Sprawdź to na
docelowym serwerze: `curl .../health` ma pokazać nazwę karty.

## API

`POST /api/v1/pomiary` (multipart): `zdjecie` (PNG), opcjonalnie `raw` (DNG), `metadane` (JSON:
`id_pomiaru` jako UUID, `numer_probki`, `kod_partii`, `id_stacji`, `czas_zdjecia`, `akwizycja`).

Ponowne wysłanie tego samego `id_pomiaru` zwraca poprzedni wynik. Kody: 400 oznacza złe dane i stacja
nie ponawia, 5xx oznacza, że stacja ponowi później.

## Podłączenie prawdziwego modelu

Nowa klasa w `analiza/analizator.py` z metodą `analizuj` i `zrodlo = "model"`, wpięta w `main.py`.
Kod modelu (`training_grainnet`) leży w repo `kamyki`. Metoda będzie potrzebowała ścieżki zdjęcia,
a do wariantu `gpu` w `Dockerfile` trzeba dołożyć zależności modelu i wagi.

## Testy

`.venv/bin/python -m pytest service/tests -q`
