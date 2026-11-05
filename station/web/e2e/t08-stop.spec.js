import { test, expect } from '@playwright/test'
import { reset, przyciskGlowny, oproznijPudelko, skalibruj, sprawdzEkran } from './pomoc.js'

test.beforeEach(async ({ request }) => {
  await reset(request)
  await request.post('/api/dev/ustawienia', { data: { czas_splywu_s: 5 } })
})

const historia = async (request) => (await request.get('/api/dev/historia')).json()

async function przytrzymaj(page, ms) {
  const przycisk = page.getByRole('button', { name: 'PRZYTRZYMAJ, ABY WZNOWIĆ' })
  await przycisk.hover()
  await page.mouse.down()
  await page.waitForTimeout(ms)
  await page.mouse.up()
}

test('STOP w ruchu: bez przytrzymania nic nie rusza, potem kalibracja na żądanie i czyszczenie', async ({ page, request }) => {
  await skalibruj(page)
  await przyciskGlowny(page, 'NOWY POMIAR')
  await expect(page.getByRole('heading', { name: 'Maszyna się przygotowuje' })).toBeVisible()
  await page.getByRole('button', { name: 'STOP' }).click()
  await expect(page.getByRole('heading', { name: 'Maszyna zatrzymana' })).toBeVisible()
  await sprawdzEkran(page)
  const przed = await historia(request)

  await przytrzymaj(page, 500)                       // za krótko: nic się nie dzieje
  await page.waitForTimeout(300)
  await expect(page.getByRole('heading', { name: 'Maszyna zatrzymana' })).toBeVisible()

  await przytrzymaj(page, 3200)
  await expect(page.getByRole('heading', { name: 'Maszyna musi się ustawić' })).toBeVisible()
  expect(await historia(request)).toEqual(przed)     // restart, ale bez żadnego ruchu

  await przyciskGlowny(page, 'USTAW MASZYNĘ')
  await expect(page.getByRole('heading', { name: 'Maszyna czyści stół' })).toBeVisible()
  await oproznijPudelko(page)
  await expect(page.getByRole('button', { name: 'NOWY POMIAR' })).toBeVisible()
})

test('STOP jest dostępny na każdym ekranie cyklu', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'STOP' })).toBeVisible()
  await przyciskGlowny(page, 'USTAW MASZYNĘ')
  await expect(page.getByRole('button', { name: 'STOP' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Maszyna gotowa' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'STOP' })).toBeVisible()
  await przyciskGlowny(page, 'NOWY POMIAR')
  await expect(page.getByRole('heading', { name: 'Wsyp próbkę do lejka' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'STOP' })).toBeVisible()
})

test('błąd makra: komunikat bez nazw makr, odblokowanie, kalibracja, czyszczenie', async ({ page, request }) => {
  await skalibruj(page)
  await request.post('/api/dev/blad', { data: { makro: 'PRZYGOTUJ', tresc: 'INTERLOCK: stol' } })
  await przyciskGlowny(page, 'NOWY POMIAR')
  await expect(page.getByRole('heading', { name: 'Wystąpił błąd' })).toBeVisible()
  await expect(page.getByText('Zabezpieczenie zatrzymało ruch maszyny.')).toBeVisible()
  await sprawdzEkran(page)
  await przyciskGlowny(page, 'ODBLOKUJ MASZYNĘ')
  await przyciskGlowny(page, 'USTAW MASZYNĘ')
  await oproznijPudelko(page)
})
