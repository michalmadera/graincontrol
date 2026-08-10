Do kontroli jakości zastosować przestrzeń **CIELAB (L\*a\*b\*)**, bo pozwala rozdzielić jasność od odcienia.

### 1. Parametry barwy każdego kamienia

Dla pikseli należących do obszaru kamienia obliczasz:

L∗

— jasność: 0 = czarny, 100 = idealnie biały.

a∗

— oś zielony ↔ czerwony; dla neutralnie białego materiału powinna być blisko 0.

b∗

— oś niebieski ↔ żółty; w przypadku białego marmuru będzie szczególnie interesująca, ponieważ pozwala wykrywać **żółknięcie/kremowy odcień**.

Dla każdego kamienia przechowywałbym przede wszystkim:

Median(L∗),Median(a∗),Median(b∗)

Mediana może być lepsza od średniej, ponieważ pojedyncze ciemne żyłki, refleksy czy cień nie będą aż tak mocno wpływały na wynik. Średnie również warto zachować jako dane surowe/statystyczne.

### 2. „Jak biały jest kamień?”

Możesz dodatkowo wprowadzić prosty wskaźnik odchylenia od neutralnej bieli. Dla chromatyczności:

Cab∗=(a∗)2+(b∗)2

Im bliżej:

a∗=0,b∗=0

tym bardziej neutralna jest barwa.

Wtedy biały marmur dobrej jakości powinien mieć jednocześnie **wysokie L∗** i **niskie Cab∗**.

Przykładowo dwa kamienie:

| Kamień | L*   | a*   | b*   | C*   | Interpretacja        |
| ------ | ---- | ---- | ---- | ---- | -------------------- |
| A      | 92   | 0.4  | 1.8  | 1.84 | jasny, neutralny     |
| B      | 82   | 1.2  | 7.5  | 7.60 | ciemniejszy, żółtawy |

Kamień B zdecydowanie bardziej odstaje od oczekiwanego białego marmuru.

### 3. Nie używałbym jednak sztywnych wartości jako głównego kryterium

Przy kontroli dostawcy lepszym rozwiązaniem jest zdefiniowanie **barwy referencyjnej** dla akceptowalnego materiału:

(Lref∗,aref∗,bref∗)

a następnie dla każdego kamienia mierzenie różnicy koloru względem wzorca za pomocą **Delta E**.

W najprostszej wersji:

ΔEab=(L∗−Lref∗)2+(a∗−aref∗)2+(b∗−bref∗)2

Im mniejsze ΔE, tym bardziej kolor kamienia odpowiada wzorcowi.

Docelowo można zastosować **CIEDE2000 (ΔE00)**, który lepiej odpowiada percepcji człowieka.

### 4. Proponowana klasyfikacja OK/NOK

Dla białego marmuru zastosowałbym **dwa warunki jednocześnie**:

L∗≥Lmin∗

oraz

ΔE00≤ΔEmax

czyli kamień musi być **wystarczająco jasny** i jednocześnie jego barwa nie może za bardzo odbiegać od wzorca.

Przykładowe progi startowe, wymagające późniejszej kalibracji na rzeczywistych próbkach:

Lmin∗=85ΔEmax=5

Wtedy:

ColorStatus={OK,NOK,L∗≥Lmin∗∧ΔE00≤ΔEmaxotherwise

### 5. Co raportować dla całej próbki

Analogicznie do kształtu przechowywałbym dla partii:

**L\*** — średnia, mediana, min/max, odchylenie standardowe;
 **a\*** — średnia i mediana;
 **b\*** — średnia i mediana;
 **ΔE00** — średnia, mediana, P90/P95;
 **Color OK [%]** — procent kamieni spełniających kryteria.

Przykładowe kryterium partii mogłoby być:

ColorOK%≥95%

oraz np.

Median(L∗)≥88P95(ΔE00)≤5

Wszystkie wartości progowe oczywiście jako **konfigurowalne**.