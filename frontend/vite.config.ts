import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Defaults must match backend/hsptl_core/config.py (DEFAULT_PORT, DEFAULT_DEV_PORT).
// Override with HSPTL_PORT / HSPTL_DEV_PORT so the proxy and the backend agree.
const backendPort = process.env.HSPTL_PORT || '8000';
const devPort = Number(process.env.HSPTL_DEV_PORT || '5173');

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '127.0.0.1',
    port: devPort,
    strictPort: true,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
    assetsDir: 'assets',
  },
});
