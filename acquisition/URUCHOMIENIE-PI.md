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

```bash
pip install -r acquisition/server/requirements.txt
# gdyby pip marudził na numpy/Pillow, można z apt:
# sudo apt install -y python3-numpy python3-pil
```

Kamera (jeśli jeszcze nie ma): `sudo apt install -y rpicam-apps`

## 3. Sprawdź kamerę (opcjonalnie)

```bash
rpicam-still --version
rpicam-hello -t 1500        # czy pokazuje obraz z kamery
```

## 4. Odpal serwer

```bash
cd ~/graincontrol
export PYTHONPATH=acquisition
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Otwórz w przeglądarce:
- na samym Pi: **http://localhost:8000**
- z innego komputera w tej sieci: **http://ADRES-IP-PI:8000** (`hostname -I` pokaże IP)

## 5. Co sprawdzić od razu (przed pierwszym zdjęciem)

W prawym górnym rogu:
- **brak plakietki „ATRAPA"** → `rpicam-still` widziany, będzie robić prawdziwe zdjęcia ✅
- **plakietka „ATRAPA (bez kamery)"** → Pi nie widzi rpicam (sprawdź instalację kamery)
- **żółty pasek** → np. brak pliku strojenia scientific; zdjęcie i tak się zrobi (domyślny tuning)

## Gdzie lądują zdjęcia

```
dane/sesja_RRRRMMDD_GGMM/
  BAD/   BAD_1.png  BAD_1.dng  BAD_2.png  BAD_2.dng …
  NICE/  NICE_1.png NICE_1.dng …
```

Domyślnie `dane/` w katalogu repo. Inny katalog:
```bash
export GRAINCONTROL_DANE=/media/usb/kruszywo-dane
```

Inny profil parametrów (domyślnie P1-scientific):
```bash
export GRAINCONTROL_PROFILE=/sciezka/do/profilu.json
```

## Jak coś nie działa

| objaw | co to znaczy / co zrobić |
|---|---|
| UI wisi „łączenie z kamerą" | stary serwer chodzi — `pkill -f "uvicorn server.main"` i odpal ponownie; w przeglądarce Ctrl+Shift+R |
| plakietka „ATRAPA" na Pi | `rpicam-still` nie na PATH → `sudo apt install rpicam-apps`, sprawdź `rpicam-hello` |
| czerwony toast po ZDJĘCIU | błąd `rpicam-still` — treść błędu jest w toaście i w terminalu |
| podgląd czarny, ale zdjęcia OK | to tylko `rpicam-vid` (podgląd) — daj znać, dostroję |

## Test bez kamery (na laptopie)

```bash
acquisition/server/run-dev.sh     # atrapa, http://127.0.0.1:8000
```
