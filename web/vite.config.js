import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// `npm run build` writes the dashboard to ../dashboard, next to the home page (index.html),
// so the home page's "Open dashboard" button (href="dashboard/") works on any static host.
// base './' keeps every asset path relative.
export default defineConfig({
  plugins: [react()],
  base: './',
  build: { outDir: '../dashboard', emptyOutDir: true },
});
