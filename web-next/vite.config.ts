import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Published at /tributary/ on GitHub Pages and at / by `trib serve`. A relative
// base works for both, so one `npm run build` serves either.
export default defineConfig(({ command }) => ({
  base: process.env.BASE || (command === 'build' ? './' : '/'),
  plugins: [react()],
}));
