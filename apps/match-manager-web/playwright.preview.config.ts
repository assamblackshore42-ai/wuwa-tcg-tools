import { defineConfig } from '@playwright/test';
import config from './playwright.config';

export default defineConfig({
  ...config,
  testMatch: '**/ui.spec.ts',
  use: { ...config.use, baseURL: 'http://127.0.0.1:1422' },
  webServer: { command: 'pnpm preview', url: 'http://127.0.0.1:1422', reuseExistingServer: false },
});
