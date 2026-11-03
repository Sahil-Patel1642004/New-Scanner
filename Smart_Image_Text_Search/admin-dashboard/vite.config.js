import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { resolveApiBase } from './src/apiBase.js';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiBase = resolveApiBase(env.VITE_API_BASE_URL, mode === 'production');

  return {
    define: {
      __SCANORA_API_BASE_URL__: JSON.stringify(apiBase),
    },
    plugins: [react()],
    server: {
      port: 5173,
    },
  };
});
