import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// Backend proxy (server/proxy.mjs) that holds the Soniox + Anthropic keys.
const PROXY_TARGET = process.env.PROXY_TARGET ?? 'http://localhost:8787';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    host: true,
    port: 5173,
    // Forward /api → backend proxy so the browser can use a same-origin base.
    proxy: { '/api': { target: PROXY_TARGET, changeOrigin: true } },
  },
  preview: {
    proxy: { '/api': { target: PROXY_TARGET, changeOrigin: true } },
  },
});
