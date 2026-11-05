import { test, expect } from '@playwright/test'
import { reset, przyciskGlowny, oproznijPudelko, skalibruj, sprawdzEkran, SERWIS } from './pomoc.js'

test.beforeEach(async ({ request }) => {
  await reset(request)
  await request.post('/api/dev/ustawienia', { data: { czas_splywu_s: 5 } })
})

async function doWyniku(page) {
  await skalibruj(page)
  await przyciskGlowny(page, 'NOWY POMIAR')
  await przyciskGlowny(page, 'PRÓBKA WSYPANA')
  await expect(page.getByRole('heading', { name: 'Analizuję…' })).toBeVisible()
}

test('wynik atrapy jest zawsze oznaczony jako TEST', async ({ page, request }) => {
  await request.post(`${SERWIS}/api/dev/wymus`, { data: { werdykt: 'akceptowalna' } })
  await doWyniku(page)
  await expect(page.getByRole('heading', { name: 'DOBRA' })).toBeVisible()
  await expect(page.getByText('TEST – wynik niemiarodajny')).toBeVisible()
  await sprawdzEkran(page)
  await przyciskGlowny(page, 'DALEJ')
  await oproznijPudelko(page)
  await expect(page.getByText('Następna próbka: nr 2')).toBeVisible()
})

test('zły werdykt pokazuje ZŁA', async ({ page, request }) => {
  await request.post(`${SERWIS}/api/dev/wymus`, { data: { werdykt: 'nieakceptowalna' } })
  await doWyniku(page)
  await expect(page.getByRole('heading', { name: 'ZŁA' })).toBeVisible()
})
