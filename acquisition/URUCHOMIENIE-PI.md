# Uruchomienie na Raspberry Pi

Narzędzie akwizycji: START SESJI → wpisz nazwę (BAD/NICE…) → ZDJĘCIE ×N → zmień nazwę.
Zapis PNG+DNG do `dane/sesja_.../NAZWA/` na zamrożonych parametrach profilu.

## 1. Pobierz kod na Pi

```bash
# jeśli repo już jest na Pi:
cd ~/graincontrol           # albo gdzie masz repo
gh auth switch -u michalmadera   # to repo prywatne (właściciel michalmadera)
git pull

# jeśli klonujesz pierwszy raz:
gh auth switch -u michalmadera
git clone https://github.com/michalmadera/graincontrol.git
cd graincontrol
```

Bundle React (`acquisition/server/static/`) jest w repo — **node na Pi niepotrzebny**.

## 2. Zależności Pythona (raz)

Na nowym Raspberry Pi OS (Bookworm) `pip install` bywa blokowany
(„externally-managed-environment"). Najpewniej **venv**:

```bash
python3 -m venv ~/gc-venv
~/gc-venv/bin/pip install -r acquisition/server/requirements.txt
```

Albo bez venv (globalnie, dla użytkownika):
```bash
pip install --user --break-system-packages fastapi "uvicorn[standard]" numpy Pillow
# gdyby numpy/Pillow marudziły, można z apt:
# sudo apt install -y python3-numpy python3-pil
```

Kamera (jeśli jeszcze nie ma): `sudo apt install -y rpicam-apps`

## 3. Sprawdź kamerę (opcjonalnie)

```bash
rpicam-still --version
rpicam-hello -t 1500        # czy pokazuje obraz z kamery
```

## 4. Odpal serwer

**Zawsze przez `python3 -m uvicorn`** (komenda `uvicorn` często nie jest na PATH).

Jeśli używasz venv:
```bash
cd ~/graincontrol
PYTHONPATH=acquisition ~/gc-venv/bin/python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Bez venv:
```bash
cd ~/graincontrol
export PYTHONPATH=acquisition
python3 -m uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Otwórz w przeglądarce:
- na samym Pi: **http://localhost:8000**
- z innego komputera w tej sieci: **http://ADRES-IP-PI:8000** (`hostname -I` pokaże IP)

## 5. Co sprawdzić od razu (przed pierwszym zdjęciem)

W prawym górnym rogu:
- **brak plakietki „ATRAPA"** → `rpicam-still` widziany, będzie robić prawdziwe zdjęcia ✅
- **plakietka „ATRAPA (bez kamery)"** → Pi nie widzi rpicam (sprawdź instalację kamery)
- **czerwony pasek „ZDJĘCIA ZABLOKOWANE"** → brak pliku strojenia z profilu albo niezgodna
  jego suma kontrolna; zdjęcia są zablokowane, bo powstałyby w innym torze obrazowym
- obok nazwa profilu i czas naświetlania — sprawdź, czy to ten, którym chcesz zbierać

## Gdzie lądują zdjęcia

```
dane/sesja_RRRRMMDD_GGMM/
  manifest.csv                 jeden wiersz na ujęcie
  journal.jsonl                dziennik: start sesji, każde ujęcie, każde odrzucenie
  BAD/   BAD_1.png  BAD_1.dng  BAD_1_meta.json  BAD_1_acquisition.json  BAD_1.sha256
  NICE/  NICE_1.png …
  odrzucone/BAD/BAD_3_123500/  ujęcie niezgodne z profilem, razem z przyczyną
```

Każde ujęcie przechodzi kontrakt akwizycji (§5) liczony z metadanych `rpicam-still`.
Odrzucenie **nie zwiększa numeru** — powtórz ujęcie, numeracja zostaje ciągła.
`*.sha256` powstaje jako ostatni i jest markerem kompletności: plik zdjęcia bez niego
to zapis przerwany i przy starcie kolejnej sesji trafia do `odrzucone/niedokonczone/`.

Domyślnie `dane/` w katalogu repo. Inny katalog:
```bash
export GRAINCONTROL_DANE=/media/usb/kruszywo-dane
```

Inny profil parametrów (domyślnie P2-scientific-20260813, 82 ms):
```bash
export GRAINCONTROL_PROFILE=/sciezka/do/profilu.json
```

## Jak coś nie działa

| objaw | co to znaczy / co zrobić |
|---|---|
| `uvicorn: command not found` | wołaj `python3 -m uvicorn ...` (nie `uvicorn ...`) |
| `No module named uvicorn` | niezainstalowany — patrz krok 2 (venv albo `pip install --user --break-system-packages`) |
| UI wisi „łączenie z kamerą" | stary serwer chodzi — `pkill -f "uvicorn server.main"` i odpal ponownie; w przeglądarce Ctrl+Shift+R |
| czerwony pasek „ZDJĘCIA ZABLOKOWANE" | profil jest niekompletny albo plik strojenia nie zgadza się z sumą kontrolną w profilu. Treść paska podaje konkretną przyczynę — nie obchodź jej, bo to jedyne zabezpieczenie przed zbieraniem materiału w innym torze obrazowym niż deklarowany |
| ujęcie „ODRZUCONE" z rozbieżnością | kamera zwróciła inne parametry niż profil. Pliki są w `odrzucone/` jako dowód; powtórz ujęcie. Powtarzające się odrzucenia oznaczają, że stanowisko się rozjechało |
| plakietka „ATRAPA" na Pi | `rpicam-still` nie na PATH → `sudo apt install rpicam-apps`, sprawdź `rpicam-hello` |
| czerwony toast po ZDJĘCIU | błąd `rpicam-still` — treść błędu jest w toaście i w terminalu |
| podgląd czarny, ale zdjęcia OK | to tylko `rpicam-vid` (podgląd) — daj znać, dostroję |

## Test bez kamery (na laptopie)

```bash
acquisition/server/run-dev.sh     # atrapa, http://127.0.0.1:8000
```
