import { expect } from '@playwright/test'

export async function reset(request) {
  const odp = await request.post('/api/dev/reset')
  expect(odp.ok()).toBeTruthy()
}

export async function przyciskGlowny(page, nazwa) {
  const przycisk = page.getByRole('button', { name: nazwa })
  await expect(przycisk).toBeVisible()
  await przycisk.click()
}

export async function skalibruj(page) {
  await page.goto('/')
  await przyciskGlowny(page, 'USTAW MASZYNĘ')
  await expect(page.getByRole('heading', { name: 'Maszyna gotowa' })).toBeVisible()
}

// Ekran robotnika nie może się przewijać ani zawierać nazw makr.
export async function sprawdzEkran(page) {
  const wymiary = await page.evaluate(() => ({
    w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight,
  }))
  expect(wymiary.w).toBeLessThanOrEqual(1280)
  expect(wymiary.h).toBeLessThanOrEqual(800)
  await expect(page.locator('body')).not.toContainText(/KALIBRUJ|PRZYGOTUJ|POMIAR|ODBLOKUJ/)
}
