import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Build wchodzi prosto do ../server/static — tam FastAPI serwuje bundle.
// base './' → ścieżki względne, żeby działało bez względu na host/port kiosku.
// Bez zasobów z sieci: wszystko (JS, CSS, czcionki) ląduje w bundlu (§12.13).
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: '../server/static',
    emptyOutDir: true,
    assetsInlineLimit: 4096,
  },
  server: {
    // dev: proxy API do uvicorna, żeby `npm run dev` gadał z backendem
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
