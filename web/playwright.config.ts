import { defineConfig, devices } from '@playwright/test'

const apiEnvironment = {
  APP_ENV: 'development',
  DATABASE_URL: process.env.PRAVAAH_E2E_DATABASE_URL ?? 'sqlite:///./var/pravaah-e2e.sqlite3',
  JWT_SECRET_KEY: 'ci-only-pravaah-e2e-signing-secret-2026',
  DEMO_USER_PASSWORD: 'PRAVAAH-E2E-Only-Password-2026!',
  CORS_ORIGINS: 'http://127.0.0.1:5173',
  EVIDENCE_STORAGE_DIR: './var/e2e-uploads',
  SMTP_HOST: '',
  SMTP_FROM: '',
}

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: 'cd .. && python -m scripts.e2e_server',
      url: 'http://127.0.0.1:8000/health/ready',
      reuseExistingServer: false,
      timeout: 60_000,
      env: apiEnvironment,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      env: { VITE_API_BASE_URL: 'http://127.0.0.1:8000/api/v1' },
    },
  ],
})
