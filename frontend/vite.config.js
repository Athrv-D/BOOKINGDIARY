import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'node:path'

export default defineConfig(({command}) =>({
  plugins: [vue(), tailwindcss()],

  base: command === 'serve' ? '/' : '/assets/booking_diary/frontend/',
  server: {
  proxy: {
    '/api': {
      target: 'http://mysite.localhost:8000',
      changeOrigin: true,
    },
    '/assets': {
      target: 'http://mysite.localhost:8000',
      changeOrigin: true,
    },
  },
},

  build: {
    outDir: resolve(
      import.meta.dirname,
      '../booking_diary/public/frontend'
    ),
    emptyOutDir: true,
    assetsDir: 'assets',
    manifest: true,
  },
}))
