import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/chat': { target: 'http://localhost:8000' },
      '/api': {
        target: 'http://localhost:8000',

      },
    },
  },
})
