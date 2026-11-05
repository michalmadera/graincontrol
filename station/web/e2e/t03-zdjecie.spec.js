import { test, expect } from '@playwright/test'
import { reset, przyciskGlowny, skalibruj, sprawdzEkran } from './pomoc.js'

test.beforeEach(async ({ request }) => {
  await reset(request)
  await request.post('/api/dev/ustawienia', { data: { czas_splywu_s: 5 } })
})

test('błąd zdjęcia daje ponowienie bez ruchu maszyny', async ({ page, request }) => {
  await skalibruj(page)
  await request.post('/api/dev/blad-zdjecia', { data: { makro: '-', tresc: 'Kamera nie odpowiada' } })
  await przyciskGlowny(page, 'NOWY POMIAR')
  await przyciskGlowny(page, 'PRÓBKA WSYPANA')
  await expect(page.getByRole('heading', { name: 'Nie udało się zrobić zdjęcia' })).toBeVisible()
  await expect(page.getByText('Kamera nie odpowiada')).toBeVisible()
  await sprawdzEkran(page)
  const przed = await (await request.get('/api/dev/historia')).json()
  await przyciskGlowny(page, 'PONÓW ZDJĘCIE')
  await expect(page.getByRole('heading', { name: 'Analizuję…' })).toBeVisible()
  expect(await (await request.get('/api/dev/historia')).json()).toEqual(przed)
})
