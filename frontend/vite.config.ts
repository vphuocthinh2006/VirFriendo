import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/auth': { target: 'http://localhost:8000', changeOrigin: true },
      '/game': { target: 'http://localhost:8000', changeOrigin: true },
      '/agents': { target: 'http://localhost:8000', changeOrigin: true },
      '/diary': { target: 'http://localhost:8000', changeOrigin: true },
      '/chat': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
        bypass(req) {
          if (req.method !== 'GET') return undefined
          const path = (req.url ?? '').split('?')[0]
          if (path === '/chat' || path === '/chat/') return '/index.html'
          return undefined
        },
      },
    },
  },
})
