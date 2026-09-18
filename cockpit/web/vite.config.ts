import tailwindcss from '@tailwindcss/vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [tailwindcss(), svelte()],
  worker: { format: 'es' },
  resolve: {
    alias: {
      'monaco-editor-css': fileURLToPath(
        new URL('./node_modules/monaco-editor/min/vs/editor/editor.main.css', import.meta.url),
      ),
    },
  },
  optimizeDeps: {
    include: ['monaco-editor', '@xterm/xterm', '@xterm/addon-fit'],
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/v1': {
        target: 'http://127.0.0.1:8788',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
