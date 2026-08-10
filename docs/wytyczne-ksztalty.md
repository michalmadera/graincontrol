## Specyfikacja oceny jakości kształtu materiału na podstawie obrazu 2D

System powinien analizować każdy wykryty kamień na podstawie jego obrysu 2D. Wyniki powinny być dostępne zarówno na poziomie pojedynczego kamienia, jak i całej analizowanej próbki/partii materiału.

### 1. Wskaźniki dla pojedynczego kamienia

Dla każdego wykrytego kamienia należy wyznaczyć co najmniej następujące cechy:

**Circularity (C)** – miara okrągłości obiektu:

C=P24πA

gdzie A oznacza pole powierzchni obiektu, a P jego obwód. Wartość zbliżona do 1 oznacza kształt zbliżony do koła. Niższe wartości wskazują na kształt wydłużony lub nieregularny.

**Aspect Ratio (AR)** – miara wydłużenia obiektu:

AR=LminorLmajor

gdzie Lmajor i Lminor oznaczają długości głównej i pomocniczej osi elipsy dopasowanej do obiektu. Wartość 1 oznacza brak wydłużenia. Wartość rośnie wraz z wydłużeniem obiektu.

**Solidity (S)** – miara zwartości/regularności obiektu:

S=AconvexA

gdzie Aconvex oznacza powierzchnię otoczki wypukłej obiektu. Wartość zbliżona do 1 oznacza zwarty, regularny kształt. Niższe wartości wskazują na występowanie wgłębień lub innych nieregularności obrysu.

Dla każdego kamienia należy zapisać wartości C, AR i S oraz wynik klasyfikacji **OK/NOK**.

### 2. Statystyki dla próbki

Dla każdej analizowanej próbki materiału system powinien podawać:

- liczbę wykrytych kamieni,
- dla Circularity: średnią i medianę,
- dla Aspect Ratio: średnią i medianę,
- dla Solidity: średnią i medianę,
- liczbę kamieni OK,
- liczbę kamieni NOK,
- procent kamieni OK,
- procent kamieni NOK.

Opcjonalnie można przechowywać również minimum, maksimum, odchylenie standardowe oraz percentyle, np. P10/P90. Nie muszą one uczestniczyć w kryterium akceptacji, ale są przydatne przy analizie stabilności jakości dostaw.

### 3. Definiowalne progi klasyfikacji pojedynczego kamienia

System powinien umożliwiać konfigurację progów niezależnie dla każdego wskaźnika.

Przykładowe wartości początkowe:

**Circularity:** C ≥ 0,70
 **Aspect Ratio:** AR ≤ 1,50
 **Solidity:** S ≥ 0,90

Wartości 0,70, 1,50 i 0,90 powinny być parametrami konfiguracyjnymi, a nie wartościami zapisanymi na stałe w algorytmie.

### 4. Klasyfikacja pojedynczego kamienia

Domyślna reguła:

**OK**, jeżeli jednocześnie:

C≥CminAR≤ARmaxS≥Smin

W przeciwnym przypadku kamień klasyfikowany jest jako **NOK**.

Dla kamienia NOK system powinien przechowywać również przyczynę odrzucenia, np. `Circularity below threshold`, `Aspect Ratio above threshold`, `Solidity below threshold`. Jeden kamień może mieć więcej niż jedną przyczynę NOK.

### 5. Kryterium akceptacji całej próbki

Podstawowym kryterium powinna być minimalna wymagana zawartość kamieni spełniających wymagania:

OK%=NtotalNOK×100%

Próg akceptacji powinien być definiowalny.

Przykładowo:

**Acceptance threshold = 95%**

Próbka jest **ACCEPTED**, jeżeli co najmniej 95% analizowanych kamieni otrzymało klasyfikację OK.

Próbka jest **REJECTED**, jeżeli odsetek kamieni OK jest niższy od skonfigurowanego progu.

### 6. Dodatkowe kryteria akceptacji na poziomie próbki

System powinien umożliwiać opcjonalne zdefiniowanie kryteriów również dla zagregowanych wartości wskaźników, np.:

**Median Circularity ≥ 0,80**
 **Median Aspect Ratio ≤ 1,30**
 **Median Solidity ≥ 0,95**

Każde takie kryterium powinno być niezależnie włączane/wyłączane i mieć definiowalny próg.

Dzięki temu można przykładowo zdefiniować końcową regułę:

**ACCEPTED**, jeżeli:

```
OK% ≥ 95% AND Median Circularity ≥ 0.80 AND Median Aspect Ratio ≤ 1.30 AND Median Solidity ≥ 0.95
```

W przeciwnym przypadku:

**REJECTED**.

### 7. Konfiguracja

Progi powinny być definiowane w ramach **specyfikacji jakości materiału** i możliwe do przypisania np. do konkretnego typu materiału, produktu lub dostawcy.

Konfiguracja powinna obejmować co najmniej: minimalną Circularity, maksymalny Aspect Ratio, minimalną Solidity, minimalny procent kamieni OK oraz opcjonalne kryteria dla średnich/median.

Takie rozdzielenie daje trzy poziomy danych: **surowe wyniki każdego kamienia → statystyki próbki → jednoznaczna decyzja ACCEPTED/REJECTED**.