import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  publicDir: resolve(__dirname, 'src/public'),
  base: './',
  resolve: {
    alias: {
      '@renderer': resolve(__dirname, 'src')
    }
  },
  plugins: [react(), tailwindcss()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    target: 'es2022',
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/three') || id.includes('@react-three')) {
            return 'vendor-three'
          }
          if (id.includes('node_modules/react-icons')) {
            return 'vendor-icons'
          }
          if (id.includes('node_modules/react/') || id.includes('node_modules/react-dom/')) {
            return 'vendor-react'
          }
          if (id.includes('node_modules/lucide-react')) {
            return 'vendor-lucide'
          }
        }
      }
    }
  }
})
