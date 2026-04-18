import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:3000',
    locale: 'en-US',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'chromium-mobile',
      use: { ...devices['iPhone 12'] },
    },
  ],
  webServer: {
    command: 'npm run build && npm start',
    url: 'http://localhost:3000/en',
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      TAROT_ENABLE_TEST_OVERRIDES: 'true',
      TAROT_SECRET: 'test-tarot-secret-for-e2e-override-only',
    },
    // The webServer env activates the test-only override contract:
    // - TAROT_ENABLE_TEST_OVERRIDES=true gates the override mechanism
    // - TAROT_SECRET provides the deterministic test secret
    // Open-path E2E tests set x-test-open: true per request → gate opens
    // Closed-path E2E tests omit the header → gate follows real schedule
  },
});
