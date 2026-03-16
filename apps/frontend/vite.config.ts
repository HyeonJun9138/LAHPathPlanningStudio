import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const frontendPort = Number(env.VITE_PORT || 5173)
  const backendUrl = env.VITE_BACKEND_URL || 'http://127.0.0.1:8000'

  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: '127.0.0.1',
      port: frontendPort,
      proxy: {
        '/api': backendUrl
      }
    },
    resolve: {
      alias: {
        'buffer/': 'buffer'
      }
    },
    optimizeDeps: {
      include: ['buffer']
    },
    build: {
      rollupOptions: {
        external: ['buffer/']
      },
      chunkSizeWarningLimit: 5000
    }
  }
})
