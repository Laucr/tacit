import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const basePath = process.env.VITE_BASE_PATH || '/';
const honchoTarget = process.env.HONCHO_BASE_URL || 'http://localhost:8787';

export default defineConfig({
  plugins: [react()],
  base: basePath,
  server: {
    port: 5175,
    strictPort: true,
    proxy: {
      // Local dev mode (base path `/`): proxy /api to Honcho.
      '/api': {
        target: honchoTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      // Gateway dev mode (base path `/memboard/`).
      '/memboard/api': {
        target: honchoTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/memboard\/api/, ''),
      },
    },
  },
  build: {
    outDir: 'dist',
  },
});
