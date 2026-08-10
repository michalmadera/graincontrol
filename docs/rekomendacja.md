Pierwotna wersja tego dokumentu powstała, gdy `photoNewParam.py` robił zdjęcie w trybie
w pełni automatycznym. Część zaleceń została już wdrożona w `photoNewParam_final.py`,
a część pierwotnych twierdzeń o pliku strojenia okazała się błędna po sprawdzeniu
źródeł — errata na końcu.

## 0. Status

| obszar | stan |
|---|---|
| ekspozycja i wzmocnienie | **zrobione** — `--shutter 65000`, `--gain 1.0` |
| balans bieli | **zrobione** — `--awbgains 2.36,2.19` |
| parametry ISP (wyostrzanie, denoise) | **do zrobienia** — działają wartości domyślne |
| plik strojenia | **do decyzji** — patrz §3, ma nieoczywisty koszt |
| ekspozycja pod biel / wzorzec bieli w kadrze | **do zrobienia** |
| zapis RAW | **do zrobienia** |
| kalibracja skali mm/px | **do zrobienia** — obecnie założenie, nie pomiar |
| korekcja flat-field | **do zrobienia**, warunkowo obowiązkowa — patrz §3 i §6 |

## 1. Powtarzalność — zrobione

| parametr | wartość | dlaczego |
| --- | --- | --- |
| `--shutter 65000` | µs, na sztywno | wyłącza AEC; bez tego każde zdjęcie ma inną ekspozycję |
| `--gain 1.0` | 1.0 | wyłącza AGC i daje najniższy szum; przy stałym świetle jasność reguluje się **czasem**, nie wzmocnieniem |
| `--awbgains 2.36,2.19` | R,B | kluczowe: białe kamyki wypełniające kadr → AWB liczyłby balans z zawartości kadru, więc kolor zmieniałby się przy każdym układzie kamyków |

Osobne `--awb off` jest zbędne — podanie niezerowego `--awbgains` samo wyłącza algorytm AWB.

Weryfikacja: `ExposureTime`, `AnalogueGain`, `DigitalGain` i `ColourGains` w metadanych
muszą być identyczne w kolejnych ujęciach. Skrypt już te pola drukuje. Dwa uzupełnienia:

- **`DigitalGain` musi wynosić 1,000.** Wartość różna od 1 oznacza, że ISP mimo wszystko
  kompensował ekspozycję cyfrowo i skala jasności jest przesunięta.
- **`ColourCorrectionMatrix` też należy logować.** Plik strojenia wybiera macierz
  z kilku–kilkunastu wariantów według oszacowanej temperatury barwowej; przy zamrożonych
  `awbgains` powinno być to deterministyczne, ale to trzeba sprawdzić, a nie założyć.

Uwaga do 65 ms: przy tak długim czasie drgania stanowiska (wentylator, przejście obok,
uderzenie w stół) rozmażą krawędzie. Warto zweryfikować serią zdjęć tej samej sceny.

## 2. Wyłączenie „upiększania" obrazu przez ISP — do zrobienia

Wartości domyślne zweryfikowane w `core/options.cpp` rpicam-apps:

| parametr | domyślnie | ustawić | czy zmienia obraz |
| --- | --- | --- | --- |
| `--sharpness` | **1.0 = „normal sharpening"** | **0** | **tak** — wyostrzanie jest teraz włączone i tworzy halo na krawędziach kamyków |
| `--denoise` | `auto`, co dla zdjęcia rozwija się do **`cdn_hq`** | **`off`** | **tak** — działa najagresywniejszy wariant colour denoise |
| `--saturation` | 1.0 | 1.0 | nie — zamek na przyszłość |
| `--contrast` | 1.0 | 1.0 | nie — zamek na przyszłość |
| `--brightness` | 0 | 0 | nie — zamek na przyszłość |

Trzy ostatnie mają domyślne wartości już neutralne, więc ich jawne ustawienie niczego
dziś nie zmienia. Robi się to po to, żeby przyszła zmiana konfiguracji, inna wersja
rpicam-apps albo inny plik strojenia nie przesunęły tonów i chromy po cichu.

`--sharpness` to **cyfrowy filtr krawędziowy w ISP, nie ostrość obiektywu** — ta pozostaje
ustawiona i zablokowana mechanicznie i programowo się jej nie zmienia. Nazwa myli.

`--denoise` steruje dwoma niezależnymi filtrami: SDN (spatial, na danych Bayera) i CDN
(colour, uśrednianie chromy w domenie YUV); `off` wyłącza oba, `cdn_off` zdejmuje tylko
CDN. Dla pomiaru barwy groźniejszy jest CDN, bo przestrzennie uśrednia chromę — miesza
a\*/b\* między sąsiadującymi kamykami i między kamykiem a tłem. Zapas na wyłączenie jest
duży: zmierzony szum własny pomiaru barwy to mediana ΔE00 = 0,21, a mediana kamyka
liczona jest z 500–900 pikseli. Po zmianie test trzeba powtórzyć i sprawdzić, czy
maski (cellpose) zachowują się tak samo na mniej wygładzonej teksturze.

## 3. Plik strojenia — nie jest darmowym zyskiem

`--tuning-file` podmienia parametry **całego ISP**: krzywą tonalną, macierze korekcji
barwy, korekcję winietowania, wyostrzanie i denoise. Bez tej flagi używany jest domyślny
`imx477.json`. Porównanie z wariantem pomiarowym, sprawdzone w repozytorium libcamera
(gałąź `vc4`):

| blok | `imx477.json` (używany teraz) | `imx477_scientific.json` |
| --- | --- | --- |
| `rpi.sharpen` | threshold 0,75 / limit 0,5 / strength 1,0 | **identyczny** |
| `rpi.contrast` → `ce_enable` | 1 — wzmocnienie kontrastu włączone | **0 — wyłączone** |
| gamma, wejście 25% | wyjście **62,0%** | wyjście **48,6%** (Rec.709) |
| `rpi.ccm` | 6 temperatur barwowych | **19 temperatur (2000–8600 K)** |
| `rpi.alsc` — korekcja winietowania | **obecny, korekcja działa** | **nieobecny, korekcji nie ma** |

Co z tego wynika:

- **Zysk jest realny**: wyłączone wzmocnienie kontrastu, łagodniejsza krzywa tonalna
  i trzykrotnie gęściej skalibrowane macierze barwy. To jest właściwy wybór do pomiaru.
- **Koszt jest ukryty**: plik scientific nie zawiera bloku ALSC, więc **traci się
  korekcję winietowania**. Obecna, bardzo płaska charakterystyka pola oświetlenia
  (rozpiętość P98 L\* w kadrze tylko 3,3 jedn.) jest po części zasługą ALSC z pliku
  domyślnego. Po przełączeniu trzeba zrobić własny flat-field ze zdjęcia jednorodnej
  białej powierzchni.
- **Zmienia się cała skala jasności.** Kamyki leżą przy DN ≈ 130–150, czyli 51–59%
  zakresu — dokładnie tam, gdzie obie krzywe różnią się najsilniej. Po przełączeniu
  obraz pociemnieje i `--shutter` trzeba dobrać od nowa.
- Plik scientific **nie wyłącza wyostrzania** — blok `rpi.sharpen` jest w obu plikach
  identyczny. To robi wyłącznie `--sharpness 0`.

Ścieżka zależy od modelu: `/usr/share/libcamera/ipa/rpi/vc4/` (Pi 4 i starsze) albo
`/usr/share/libcamera/ipa/rpi/pisp/` (Pi 5). Obecność pliku sprawdzić na urządzeniu.

Kolejność ma znaczenie: przełączać **przed** rozpoczęciem zbierania danych pomiarowych,
razem z flat-fieldem i nowym `--shutter`. Zmiana strojenia w trakcie unieważnia wszystko,
co zebrano wcześniej.

## 4. Ekspozycja pod białe obiekty

Automat mierzyłby średnią z kadru i prześwietlał kamyki; po przejściu na manual problem
znika, ale dobór czasu trzeba zrobić świadomie.

Stan obecny na `stones1.png`: maksimum w kadrze to 203 DN, **nic nie jest wyklipowane**
(0,000% pikseli ≥ 254). Ekspozycja jest więc bezpieczna, ale zostawia zapas — najjaśniejszy
piksel całego kadru odpowiada L\* = 76. Docelowo histogram najjaśniejszych pikseli
powinien sięgać ~85–90% zakresu (220–230 z 255), nigdy 255. Po zmianie pliku strojenia
(§3) trzeba to ustawić od nowa.

Odniesieniem do dobrania czasu powinien być **wzorzec bieli umieszczony w kadrze**, a nie
najjaśniejszy kamyk. Bez wzorca skala L\* nie jest do niczego zakotwiczona: L\* = 100 nie
odpowiada niczemu fizycznemu, a zmierzona jasność kamyka opisuje ekspozycję, nie materiał.

## 5. Format danych

`--encoding png` jest OK (bezstratny), ale to nadal 8-bit po gammie i po całym ISP.
**`--raw` należy traktować jako obowiązkowe**, nie opcjonalne: DNG powstaje przed ISP,
więc jest odporny na wszystkie ustawienia z §2 i §3. Jeśli którekolwiek zamrożenie okaże
się złym wyborem, z DNG da się przeliczyć cały zebrany materiał; z PNG nie odzyska się nic.
Przy badaniu obliczonym na dziesiątki próbek to jest warunek odwracalności całego
przedsięwzięcia.

Pełna rozdzielczość 4056×3040 jest właściwa (bez binningu, maksimum detalu).

Opcjonalnie `--immediate` — przy w pełni ręcznych ustawieniach pomija okres preview,
przez co przechwycenie jest szybsze i bardziej deterministyczne.

## 6. Poza kodem — optyka i scena

- **Przysłona**: optimum ok. **f/4–f/5.6**. Piksel IMX477 ma 1,55 µm, więc powyżej f/8
  dyfrakcja wyraźnie zmiękcza obraz — domykanie „dla głębi ostrości" pogorszy wynik.
- **Ostrość**: ustawić raz przy docelowych 29 cm i **zablokować** (śruba/klej) — to
  najczęstsze źródło niepowtarzalności na takich stanowiskach.
- **Kalibracja skali**: nadal niezrobiona. `analiza/an3.py` przyjmuje 35,9 µm/px jako
  **założenie** (12 mm @ 290 mm), nie pomiar. Bez sfotografowania wzorca (linijka,
  szachownica) wszystkie wielkości kamyków są tylko w pikselach.
- **Wzorzec bieli i szarości w kadrze**: stała pozycja poza obszarem materiału, w każdym
  zdjęciu. Daje trzy rzeczy naraz — zakotwiczenie skali L\*, punkt neutralny do korekty
  offsetu a\*/b\* i detektor dryfu oświetlenia między sesjami.
- **Vignetting**: **korekta wcześniejszego zalecenia.** Pierwotnie napisałem, że rozwiązuje
  to tuning scientific — jest odwrotnie, ten plik korekcję winietowania **usuwa** (§3).
  Flat-field ze zdjęcia jednorodnego tła jest więc obowiązkowy, jeśli przechodzimy na
  scientific, i opcjonalny, jeśli zostajemy przy domyślnym pliku.

## Docelowa komenda

```
rpicam-still -o out.png --encoding png --width 4056 --height 3040 \
  --tuning-file /usr/share/libcamera/ipa/rpi/vc4/imx477_scientific.json \
  --shutter <dobrać od nowa po zmianie strojenia> --gain 1.0 \
  --awbgains 2.36,2.19 \
  --sharpness 0 --denoise off \
  --saturation 1.0 --contrast 1.0 --brightness 0 \
  --immediate --raw \
  --metadata meta.json --metadata-format json
```

`--shutter` jest jedyną wartością do ponownego dobrania; `--awbgains 2.36,2.19` pochodzi
już z pomiaru i zostaje.

## Errata względem pierwszej wersji

| twierdzenie pierwotne | jak jest naprawdę |
| --- | --- |
| plik scientific ma „gamma bliską liniowej" | ma krzywą Rec.709 (odcinek liniowy o nachyleniu 4,5) — znacznie łagodniejszą od domyślnej, ale nie liniową |
| plik scientific ma „jednostkową macierz kolorów" | ma 19 skalibrowanych macierzy CCM zamiast 6 — i to jest jego zaleta, nie brak macierzy |
| plik scientific ma „brak wyostrzania i denoise" | blok `rpi.sharpen` jest identyczny jak w pliku domyślnym; wyostrzanie zdejmuje tylko `--sharpness 0` |
| tuning scientific rozwiązuje problem vignettingu | usuwa blok ALSC, czyli **pogarsza** równomierność pola; flat-field staje się obowiązkowy |
| `--awb off` + `--awbgains` | samo `--awbgains` wyłącza AWB, drugi przełącznik jest zbędny |

Źródła weryfikacji: `imx477.json` i `imx477_scientific.json` w repozytorium
raspberrypi/libcamera (`src/ipa/rpi/vc4/data/`), `core/options.cpp` i `core/rpicam_app.cpp`
w raspberrypi/rpicam-apps.

Szersze omówienie warstwy pomiarowej i tego, co z tych ustawień wynika dla zbierania
danych do progów, jest w `spec-analizy-barwy.md` §2.
