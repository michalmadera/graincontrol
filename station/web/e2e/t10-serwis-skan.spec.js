import { test, expect } from '@playwright/test'
import { reset, przyciskGlowny, skalibruj, sprawdzEkran } from './pomoc.js'

test.beforeEach(async ({ request }) => { await reset(request) })

async function wejdzDoSerwisu(page, ms = 5200) {
  await page.getByTestId('logo').hover()
  await page.mouse.down()
  await page.waitForTimeout(ms)
  await page.mouse.up()
}

test('krótkie dotknięcie nazwy nie otwiera serwisu, przytrzymanie 5 s tak', async ({ page }) => {
  await skalibruj(page)
  await wejdzDoSerwisu(page, 500)
  await page.waitForTimeout(200)
  await expect(page.getByRole('heading', { name: 'Tryb serwisowy' })).toHaveCount(0)
  await wejdzDoSerwisu(page)
  await expect(page.getByRole('heading', { name: 'Tryb serwisowy' })).toBeVisible()
  await expect(page.getByAltText('Podgląd kamery')).toBeVisible()
  await sprawdzEkran(page)
})

test('ruch ręczny idzie do maszyny, a po wyjściu jest ekran gotowości', async ({ page, request }) => {
  await skalibruj(page)
  await wejdzDoSerwisu(page)
  await page.getByRole('button', { name: 'Stół w górę 5 mm' }).click()
  await expect.poll(async () => (await request.get('/api/dev/historia')).json()).toContain('GORA_5MM')
  await expect(page.getByRole('button', { name: 'WYJDŹ' })).toBeEnabled()
  await przyciskGlowny(page, 'WYJDŹ')
  await expect(page.getByRole('heading', { name: 'Maszyna gotowa' })).toBeVisible()
})

test('skanowanie: domyślnie wyłączone, po włączeniu wymaga poprawnego kodu', async ({ page }) => {
  await skalibruj(page)
  await expect(page.getByLabel('Zeskanuj kod partii')).toHaveCount(0)
  await wejdzDoSerwisu(page)
  await page.getByRole('button', { name: /Skanowanie kodów: wyłączone/ }).click()
  await expect(page.getByRole('button', { name: /Skanowanie kodów: włączone/ })).toBeVisible()
  await przyciskGlowny(page, 'WYJDŹ')
  await expect(page.getByLabel('Zeskanuj kod partii')).toBeFocused()
  await expect(page.getByRole('button', { name: 'NOWY POMIAR' })).toHaveCount(0)

  await page.keyboard.type('ZLYKOD')
  await page.keyboard.press('Enter')
  await expect(page.getByRole('alert')).toContainText('Błędny kod partii')
  await expect(page.getByText('Następna próbka: nr 1')).toBeVisible()

  await page.keyboard.type('ABCDE12345')
  await page.keyboard.press('Enter')
  await expect(page.getByText('Próbka nr 1')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Wsyp próbkę do lejka' })).toBeVisible()
})

test('zmiana czasu spływu jest zapamiętana i pilnuje minimum', async ({ page }) => {
  await skalibruj(page)
  await wejdzDoSerwisu(page)
  await expect(page.getByRole('status', { name: 'Czas spływu' })).toHaveText('30 s')
  await page.getByRole('button', { name: 'Czas spływu: więcej' }).click()
  await expect(page.getByRole('status', { name: 'Czas spływu' })).toHaveText('35 s')
  await expect(page.getByRole('status', { name: 'Szczelina' })).toHaveText('0.5 mm')
  await page.getByRole('button', { name: 'Szczelina: mniej' }).click()
  await expect(page.getByRole('status', { name: 'Szczelina' })).toHaveText('0.5 mm')
  await page.reload()
  await expect(page.getByRole('status', { name: 'Czas spływu' })).toHaveText('35 s')
})
