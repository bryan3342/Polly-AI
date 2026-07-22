import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // base: '/Polly-AI/',  ← only needed for GitHub Pages

  // In production the frontend and backend are one origin (FastAPI serves the
  // built SPA), so the client derives the WebSocket URL from window.location.
  // In dev they are split across :5173 and :8000, so proxy the backend routes
  // to keep that same-origin assumption true here too.
  server: {
    proxy: {
      '/ws': { target: 'ws://localhost:8000', ws: true },
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
