import { test, expect } from '@playwright/test'
import { randomUUID } from 'node:crypto'

const SERWIS = 'http://127.0.0.1:8102'
const PNG = Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), Buffer.alloc(32)])

function formularz(id) {
  return {
    zdjecie: { name: 'zdjecie.png', mimeType: 'image/png', buffer: PNG },
    metadane: JSON.stringify({
      id_pomiaru: id, numer_probki: 1, id_stacji: 'stacja-1', czas_zdjecia: '2026-11-05T10:00:00+00:00',
    }),
  }
}

test('serwis zgłasza stan i przyjmuje zdjęcie po HTTP', async ({ request }) => {
  const zdrowie = await (await request.get(`${SERWIS}/health`)).json()
  expect(zdrowie.status).toBe('ok')
  const id = randomUUID()
  const pierwsza = await request.post(`${SERWIS}/api/v1/pomiary`, { multipart: formularz(id) })
  expect(pierwsza.ok()).toBeTruthy()
  const wynik = await pierwsza.json()
  expect(wynik.zrodlo_wyniku).toBe('atrapa')
  const druga = await request.post(`${SERWIS}/api/v1/pomiary`, { multipart: formularz(id) })
  expect(await druga.json()).toEqual(wynik)
})
