import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Published under /tributary/next/ on GitHub Pages, next to version 1 (the
// workflow sets BASE), and under /next/ by `trib serve`. A relative base works
// for both, so a plain `npm run build` is what trib serve needs.
export default defineConfig(({ command }) => ({
  base: process.env.BASE || (command === 'build' ? './' : '/'),
  plugins: [react()],
}));
