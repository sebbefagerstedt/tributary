import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Published under /tributary/next/ on GitHub Pages, next to version 1. The
// workflow sets BASE; locally the app runs at the root.
export default defineConfig({
  base: process.env.BASE || '/',
  plugins: [react()],
});
