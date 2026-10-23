import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: './tests/ui', testMatch: '**/*.spec.mjs', workers: 1, timeout: 30_000,
  use: { baseURL: 'http://127.0.0.1:18791', headless: true, channel: process.env.EVOLVECLAW_BROWSER_CHANNEL, screenshot: 'only-on-failure' },
  webServer: { command: 'node tests/ui/fixture-server.mjs', url: 'http://127.0.0.1:18791', reuseExistingServer: false, timeout: 30_000 },
  reporter: [['list'], ['json', { outputFile: 'artifacts/ui-results.json' }]], outputDir: 'artifacts/ui-tests' });
