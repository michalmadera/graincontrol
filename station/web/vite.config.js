import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Bundle ląduje w backendzie: Pi nie ma Node, a kiosk nie może sięgać do sieci po zasoby.
export default defineConfig({
  plugins: [react()],
  base: './',
  build: { outDir: '../stacja/static', emptyOutDir: true, assetsInlineLimit: 4096 },
  server: { proxy: { '/api': { target: 'http://127.0.0.1:8100', changeOrigin: true } } },
})
