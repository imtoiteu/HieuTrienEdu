import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end configuration.
 *
 * `E2E_BASE_URL` lets the suite run against an already-running dev server (which is how it is run
 * locally, since a cold Next.js dev compile can exceed a sensible webServer timeout). When it is
 * unset, Playwright starts the dev server itself.
 *
 * The API must be running and seeded — see docs/DEVELOPMENT.md.
 */
const baseURL = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:3000';

export default defineConfig({
  testDir: './e2e',
  // Journeys share one seeded student, so parallel workers would race on their mastery data.
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  timeout: 90_000,
  expect: { timeout: 15_000 },

  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    // Next.js dev compiles a route on first visit, which can take a while on a cold cache.
    actionTimeout: 20_000,
    navigationTimeout: 90_000,
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['Pixel 5'] } },
  ],

  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: 'npm run dev',
        url: baseURL,
        reuseExistingServer: true,
        timeout: 180_000,
      },
});
