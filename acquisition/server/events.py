"""Szyna zdarzeń SSE (§12.11 `/api/events`).

Postęp ujęcia i zmiany stanu kamery idą strumieniem, nie odpytywaniem (§12.13):
operator ma widzieć etap *zatrzymanie podglądu → ekspozycja → zapis → QC* bez
opóźnienia interwału. Jeden proces roboczy (`uvicorn --workers 1`), więc szyna
jest procesowa: publikacja rozsyła do wszystkich otwartych subskrypcji.
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def publish(self, kind: str, **data) -> None:
        """Nieblokująca publikacja zdarzenia do wszystkich subskrybentów."""
        payload = json.dumps({"kind": kind, **data}, ensure_ascii=False)
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass  # wolny konsument nie może zablokować ujęcia

    async def subscribe(self) -> AsyncIterator[str]:
        """Strumień gotowych ramek `text/event-stream` dla jednego klienta."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.add(queue)
        try:
            # przywitanie, żeby klient od razu widział otwarte połączenie
            yield "event: hello\ndata: {}\n\n"
            while True:
                payload = await queue.get()
                yield f"data: {payload}\n\n"
        finally:
            self._subscribers.discard(queue)
