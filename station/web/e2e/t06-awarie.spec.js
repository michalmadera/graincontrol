import { test, expect } from '@playwright/test'
import { reset, przyciskGlowny, skalibruj, sprawdzEkran, SERWIS } from './pomoc.js'

test.beforeEach(async ({ request }) => {
  await reset(request)
  await request.post('/api/dev/ustawienia', { data: { czas_splywu_s: 5 } })
})

async function pomiarDoAnalizy(page) {
  await przyciskGlowny(page, 'NOWY POMIAR')
  await przyciskGlowny(page, 'PRÓBKA WSYPANA')
}

test('wyłączony serwer nie zatrzymuje pracy, a wynik dochodzi po powrocie', async ({ page, request }) => {
  await skalibruj(page)
  await request.post('/api/dev/serwis', { data: { adres: 'http://127.0.0.1:9' } })
  await pomiarDoAnalizy(page)
  await expect(page.getByRole('heading', { name: 'Wynik po przywróceniu łączności' })).toBeVisible()
  await expect(page.getByText('Brak łączności z serwerem · w kolejce: 1')).toBeVisible()
  await sprawdzEkran(page)
  await przyciskGlowny(page, 'DALEJ')
  await expect(page.getByText('Następna próbka: nr 2')).toBeVisible()
  await request.post('/api/dev/serwis', { data: { adres: SERWIS } })
  await expect(page.getByLabel('Ostatnie wyniki')).toContainText(/Próbka 1: (DOBRA|ZŁA) \(TEST\)/)
  await expect(page.getByText('Brak łączności z serwerem')).toHaveCount(0)
})

test('odrzucenie przez serwer prosi o wezwanie serwisu', async ({ page, request }) => {
  await skalibruj(page)
  await request.post(`${SERWIS}/api/dev/wymus`, { data: { status: 422 } })
  await pomiarDoAnalizy(page)
  await expect(page.getByRole('heading', { name: 'Błąd analizy — powiadom serwis' })).toBeVisible()
})

test('pełna kolejka blokuje kolejny pomiar', async ({ page, request }) => {
  await request.post('/api/dev/ustawienia', { data: { limit_kolejki: 1 } })
  await skalibruj(page)
  await request.post('/api/dev/serwis', { data: { adres: 'http://127.0.0.1:9' } })
  await pomiarDoAnalizy(page)
  await przyciskGlowny(page, 'DALEJ')
  await expect(page.getByText('Kolejka pełna — powiadom serwis')).toBeVisible()
  await expect(page.getByRole('button', { name: 'NOWY POMIAR' })).toHaveCount(0)
})
