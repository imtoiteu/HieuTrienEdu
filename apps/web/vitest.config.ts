import path from 'node:path';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // Playwright specs live in e2e/ and must not be picked up by vitest.
    include: ['src/**/*.test.{ts,tsx}', '../../packages/*/src/**/*.test.{ts,tsx}'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@hietedu/ui': path.resolve(__dirname, '../../packages/ui/src/index.ts'),
      '@hietedu/localization': path.resolve(__dirname, '../../packages/localization/src/index.ts'),
      '@hietedu/curriculum': path.resolve(__dirname, '../../packages/curriculum/src/index.ts'),
      '@hietedu/exercise-engine': path.resolve(
        __dirname,
        '../../packages/exercise-engine/src/index.ts',
      ),
      '@hietedu/analytics': path.resolve(__dirname, '../../packages/analytics/src/index.ts'),
      '@hietedu/ai': path.resolve(__dirname, '../../packages/ai/src/index.ts'),
    },
  },
});
