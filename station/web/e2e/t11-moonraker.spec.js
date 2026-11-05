import { test, expect } from '@playwright/test'
import { spawn } from 'node:child_process'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { przyciskGlowny } from './pomoc.js'

const tutaj = path.dirname(fileURLToPath(import.meta.url))
const repo = path.resolve(tutaj, '../../..')
const PORT = 8105
const PORT_MOONRAKERA = 8104
const ADRES = `http://127.0.0.1:${PORT}`
let procesy = []

test.beforeAll(async ({ request }) => {
  procesy.push(spawn(path.join(repo, '.venv/bin/python'), [path.join(repo, 'station/tests/atrapa_moonrakera.py'), String(PORT_MOONRAKERA)], { stdio: 'ignore' }))
  procesy.push(spawn(path.join(tutaj, 'uruchom-backend.sh'), {
    env: {
      ...process.env,
      PORT: String(PORT),
      STACJA_MASZYNA_E2E: 'moonraker',
      STACJA_MOONRAKER: `ws://127.0.0.1:${PORT_MOONRAKERA}/websocket`,
      STACJA_DANE_STALE: mkdtempSync(path.join(tmpdir(), 'stacja-mr-')),
    },
    stdio: 'ignore',
  }))
  await expect.poll(async () => {
    try { return (await (await request.get(`${ADRES}/api/stan`)).json()).ekran } catch { return null }
  }, { timeout: 15_000 }).toBe('kalibracja')
})

test.afterAll(() => { procesy.forEach((p) => p.kill('SIGKILL')); procesy = [] })

test('przez klienta Moonrakera: kalibracja i STOP z tego samego ekranu', async ({ page }) => {
  await page.goto(ADRES)
  await przyciskGlowny(page, 'KALIBRACJA')
  await expect(page.getByRole('heading', { name: 'Maszyna gotowa' })).toBeVisible()
  await przyciskGlowny(page, 'NOWY POMIAR')
  await expect(page.getByRole('heading', { name: 'Wsyp próbkę do lejka' })).toBeVisible()
  await page.getByRole('button', { name: 'STOP' }).click()
  await expect(page.getByRole('heading', { name: 'Maszyna zatrzymana' })).toBeVisible()
})
