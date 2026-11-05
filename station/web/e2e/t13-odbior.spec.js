import { test, expect } from '@playwright/test'
import { reset, przyciskGlowny, skalibruj } from './pomoc.js'

test.beforeEach(async ({ request }) => {
  await reset(request)
  await request.post('/api/dev/polacz')
})

test('nieudany STOP jest widoczny i ponawiany, aż maszyna stanie', async ({ page, request }) => {
  await skalibruj(page)
  await request.post('/api/dev/rozlacz')
  await page.getByRole('button', { name: 'STOP' }).click()
  await expect(page.getByRole('alert')).toContainText('STOP NIE DOTARŁ DO MASZYNY')
  await request.post('/api/dev/polacz')
  await expect(page.getByRole('heading', { name: 'Maszyna zatrzymana' })).toBeVisible()
  await expect(page.getByText('STOP NIE DOTARŁ')).toHaveCount(0)
})

test('STOP zostaje na ekranie i zgłasza porażkę, gdy stacja nie odpowiada', async ({ page }) => {
  await skalibruj(page)
  await page.route('**/api/**', (trasa) => trasa.abort())
  await expect(page.getByRole('heading', { name: 'Brak połączenia ze stacją' })).toBeVisible()
  await page.getByRole('button', { name: 'STOP' }).click()
  await expect(page.getByRole('alert')).toContainText('STOP NIE DOTARŁ DO MASZYNY')
})

test('podwójne dotknięcie nie naciska przycisku na następnym ekranie', async ({ page, request }) => {
  await skalibruj(page)
  await page.getByRole('button', { name: 'NOWY POMIAR' }).dblclick()
  await expect(page.getByRole('heading', { name: 'Wsyp próbkę do lejka' })).toBeVisible()
  const historia = await (await request.get('/api/dev/historia')).json()
  expect(historia).toEqual(['KALIBRUJ', 'PRZYGOTUJ'])
  await przyciskGlowny(page, 'PRÓBKA WSYPANA')
})

test('zdjęcie można porzucić, a stół zostaje wyczyszczony', async ({ page, request }) => {
  await request.post('/api/dev/ustawienia', { data: { czas_splywu_s: 5 } })
  await skalibruj(page)
  await request.post('/api/dev/blad-zdjecia', { data: { makro: '-', tresc: 'Kamera nie odpowiada' } })
  await przyciskGlowny(page, 'NOWY POMIAR')
  await przyciskGlowny(page, 'PRÓBKA WSYPANA')
  await page.getByRole('button', { name: 'Zakończ bez zdjęcia' }).click()
  await expect(page.getByRole('heading', { name: 'Maszyna czyści stół' })).toBeVisible()
})
