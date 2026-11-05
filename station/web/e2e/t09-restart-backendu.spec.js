import { test, expect } from '@playwright/test'
import { spawn } from 'node:child_process'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { przyciskGlowny, oproznijPudelko } from './pomoc.js'

const tutaj = path.dirname(fileURLToPath(import.meta.url))
const PORT = 8103
const ADRES = `http://127.0.0.1:${PORT}`
const dane = mkdtempSync(path.join(tmpdir(), 'stacja-restart-'))
let proces

async function wlacz(request) {
  proces = spawn(path.join(tutaj, 'uruchom-backend.sh'), {
    env: { ...process.env, PORT: String(PORT), STACJA_DANE_STALE: dane },
    stdio: 'ignore',
  })
  await expect.poll(async () => {
    try { return (await request.get(`${ADRES}/api/stan`)).ok() } catch { return false }
  }, { timeout: 15_000 }).toBeTruthy()
}

function wylacz() {
  return new Promise((gotowe) => { proces.once('exit', gotowe); proces.kill('SIGKILL') })
}

test.afterEach(async () => { if (proces && proces.exitCode === null) await wylacz() })

test('nagły restart stacji w trakcie cyklu: czyszczenie, a numer się nie powtarza', async ({ page, request }) => {
  await wlacz(request)
  await page.goto(ADRES)
  await przyciskGlowny(page, 'KALIBRACJA')
  await przyciskGlowny(page, 'NOWY POMIAR')
  await expect(page.getByRole('heading', { name: 'Wsyp próbkę do lejka' })).toBeVisible()
  await wylacz()
  await expect(page.getByRole('heading', { name: 'Brak połączenia ze stacją' })).toBeVisible()

  await wlacz(request)
  await przyciskGlowny(page, 'KALIBRACJA')       // atrapa maszyny wstała od zera, jak po zaniku prądu
  await expect(page.getByRole('heading', { name: 'Maszyna czyści stół' })).toBeVisible()
  await oproznijPudelko(page)
  await expect(page.getByText('Następna próbka: nr 2')).toBeVisible()
})
