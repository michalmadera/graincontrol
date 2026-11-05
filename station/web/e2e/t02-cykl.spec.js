import { test, expect } from '@playwright/test'
import { reset, przyciskGlowny, skalibruj, sprawdzEkran } from './pomoc.js'

test.beforeEach(async ({ request }) => {
  await reset(request)
  await request.post('/api/dev/ustawienia', { data: { czas_splywu_s: 40 } })
})

test('pomiar prowadzi krok po kroku aż do analizy', async ({ page, request }) => {
  await skalibruj(page)
  await expect(page.getByText('Następna próbka: nr 1')).toBeVisible()
  await przyciskGlowny(page, 'NOWY POMIAR')
  await expect(page.getByRole('heading', { name: 'Wsyp próbkę do lejka' })).toBeVisible()
  await expect(page.getByText('Próbka nr 1')).toBeVisible()
  await expect(page.locator('[aria-current=step]')).toContainText('Wsyp próbkę')
  await sprawdzEkran(page)
  await przyciskGlowny(page, 'PRÓBKA WSYPANA')
  await expect(page.getByRole('heading', { name: 'Kamyki spływają' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Maszyna rozgarnia próbkę' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Analizuję…' })).toBeVisible()
  const historia = await (await request.get('/api/dev/historia')).json()
  expect(historia).toEqual(['KALIBRUJ', 'PRZYGOTUJ', 'POMIAR'])
})

test('anulowanie nie rusza maszyny, a numer nie wraca do obiegu', async ({ page, request }) => {
  await skalibruj(page)
  await przyciskGlowny(page, 'NOWY POMIAR')
  await expect(page.getByRole('heading', { name: 'Wsyp próbkę do lejka' })).toBeVisible()
  await page.getByRole('button', { name: 'Anuluj' }).click()
  await expect(page.getByRole('heading', { name: 'Maszyna musi się ustawić' })).toBeVisible()
  expect(await (await request.get('/api/dev/historia')).json()).toEqual(['KALIBRUJ', 'PRZYGOTUJ'])
  await przyciskGlowny(page, 'USTAW MASZYNĘ')
  await expect(page.getByText('Następna próbka: nr 2')).toBeVisible()
})
