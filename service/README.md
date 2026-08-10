# service — serwis analizujący

Usługa na serwerze z GPU. Przyjmuje pomiar przez REST API (zdjęcie + metadane), wykonuje
analizę obrazu, wyznacza werdykt na podstawie progu z profilu oceny, prowadzi stany dostawy
i trwale zapisuje wszystko do bazy oraz archiwum zdjęć.

Jedyne miejsce, w którym żyje logika reguły 2 z 3 — wspólne dla stacji i panelu.
Żądania są idempotentne po identyfikatorze pomiaru nadanym przez stację (warunek konieczny
dla bufora i retry).

Profile oceny wyłącznie czyta z [../profiles/](../profiles/) — nigdy ich nie modyfikuje.

Specyfikacja: [../docs/spec-operacyjny.md](../docs/spec-operacyjny.md) §5.6
