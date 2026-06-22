import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const STORAGE_STATE = path.resolve(__dirname, 'tests/.auth/session.json')

export default defineConfig({
  testDir: './tests',
  timeout: 30000,
  preserveOutput: 'never',
  fullyParallel: true,
  workers: 2,
  expect: {
    timeout: 10000
  },
  reporter: [
    ['list'],
    ['json', { outputFile: 'test-results/stage2-results.json' }]
  ],
  use: {
    baseURL: 'http://localhost:5174',
    screenshot: 'off',
    trace: 'off',
    video: 'off'
  },
  webServer: {
    command: 'npm run dev',
    port: 5174,
    reuseExistingServer: true
  },
  projects: [
    // --- Auth setup (runs first) ---
    {
      name: 'setup',
      testMatch: /fixtures\/auth\.setup\.ts$/
    },
    // --- Tests that require an authenticated session ---
    {
      name: 'logged-in',
      dependencies: ['setup'],
      use: {
        storageState: STORAGE_STATE
      },
      testMatch: /stage2\/.*\.spec\.ts$/
    },
    // --- Tests that do NOT require auth (default) ---
    {
      name: 'default',
      testIgnore: [
        /stage2\/.*\.spec\.ts$/,
        /fixtures\/.*\.setup\.ts$/
      ]
    }
  ]
})
