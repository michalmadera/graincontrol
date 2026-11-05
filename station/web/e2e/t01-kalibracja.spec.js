import { test, expect } from '@playwright/test'
import { reset, przyciskGlowny, skalibruj, sprawdzEkran } from './pomoc.js'

test.beforeEach(async ({ request }) => { await reset(request) })

test('po starcie maszyna nie rusza sama, dopiero po naciśnięciu', async ({ page, request }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Maszyna musi się ustawić' })).toBeVisible()
  await sprawdzEkran(page)
  expect(await (await request.get('/api/dev/historia')).json()).toEqual([])
  await przyciskGlowny(page, 'USTAW MASZYNĘ')
  await expect(page.getByRole('heading', { name: 'Maszyna się ustawia' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Maszyna gotowa' })).toBeVisible()
  expect(await (await request.get('/api/dev/historia')).json()).toEqual(['KALIBRUJ'])
})

test('restart maszyny zawsze wraca do kalibracji', async ({ page, request }) => {
  await skalibruj(page)
  await request.post('/api/dev/restart')
  await expect(page.getByRole('heading', { name: 'Maszyna musi się ustawić' })).toBeVisible()
})

test('utrata połączenia pokazuje komunikat, a powrót wraca do pracy', async ({ page, request }) => {
  await page.goto('/')
  await request.post('/api/dev/rozlacz')
  await expect(page.getByRole('heading', { name: 'Brak połączenia z maszyną' })).toBeVisible()
  await request.post('/api/dev/polacz')
  await expect(page.getByRole('heading', { name: 'Maszyna musi się ustawić' })).toBeVisible()
})

test('przeładowanie strony nie gubi stanu', async ({ page }) => {
  await skalibruj(page)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Maszyna gotowa' })).toBeVisible()
})
