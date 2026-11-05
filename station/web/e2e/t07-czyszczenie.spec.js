import { test, expect } from '@playwright/test'
import { reset, przyciskGlowny, oproznijPudelko, skalibruj, sprawdzEkran } from './pomoc.js'

test.beforeEach(async ({ request }) => {
  await reset(request)
  await request.post('/api/dev/ustawienia', { data: { czas_splywu_s: 5 } })
})

test('po wyniku maszyna czyści stół i prosi o opróżnienie pudełka', async ({ page, request }) => {
  await skalibruj(page)
  await przyciskGlowny(page, 'NOWY POMIAR')
  await przyciskGlowny(page, 'PRÓBKA WSYPANA')
  await przyciskGlowny(page, 'DALEJ')
  await expect(page.getByRole('heading', { name: 'Maszyna czyści stół' })).toBeVisible()
  await sprawdzEkran(page)
  await expect(page.getByRole('heading', { name: 'Opróżnij pudełko na kamyki' })).toBeVisible()
  await sprawdzEkran(page)
  const historia = await (await request.get('/api/dev/historia')).json()
  expect(historia.slice(-2)).toEqual(['PRZYGOTUJ SZCZELINA=0.5', 'POMIAR'])
  await oproznijPudelko(page)
  await expect(page.getByRole('button', { name: 'NOWY POMIAR' })).toBeVisible()
})

test('anulowanie po częściowym wsypaniu wymusza kalibrację i czyszczenie', async ({ page, request }) => {
  await skalibruj(page)
  await przyciskGlowny(page, 'NOWY POMIAR')
  await expect(page.getByRole('heading', { name: 'Wsyp próbkę do lejka' })).toBeVisible()
  await page.getByRole('button', { name: 'Anuluj' }).click()
  await przyciskGlowny(page, 'USTAW MASZYNĘ')
  await expect(page.getByRole('heading', { name: 'Maszyna czyści stół' })).toBeVisible()
  await oproznijPudelko(page)
  const historia = await (await request.get('/api/dev/historia')).json()
  expect(historia).toEqual(['KALIBRUJ', 'PRZYGOTUJ', 'KALIBRUJ', 'PRZYGOTUJ SZCZELINA=0.5', 'POMIAR'])
})

test('restart maszyny w trakcie cyklu wymusza czyszczenie przed kolejną próbką', async ({ page, request }) => {
  await skalibruj(page)
  await przyciskGlowny(page, 'NOWY POMIAR')
  await expect(page.getByRole('heading', { name: 'Wsyp próbkę do lejka' })).toBeVisible()
  await request.post('/api/dev/restart')
  await przyciskGlowny(page, 'USTAW MASZYNĘ')
  await expect(page.getByRole('heading', { name: 'Maszyna czyści stół' })).toBeVisible()
})
