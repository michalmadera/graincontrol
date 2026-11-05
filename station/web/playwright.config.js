import { defineConfig } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const tutaj = path.dirname(fileURLToPath(import.meta.url))
export const PORT = 8101

// Jeden proces backendu i jeden stan, więc testy idą kolejno, a każdy zaczyna od /api/dev/reset.
export default defineConfig({
  testDir: './e2e',
  workers: 1,
  fullyParallel: false,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    viewport: { width: 1280, height: 800 },
    hasTouch: true,
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: path.join(tutaj, 'e2e', 'uruchom-backend.sh'),
    url: `http://127.0.0.1:${PORT}/api/stan`,
    reuseExistingServer: false,
    stdout: 'pipe',
    stderr: 'pipe',
  },
})
