import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const STORAGE_STATE = path.resolve(__dirname, '../tests/stage2/e2e/.auth/session.json')

const testEnvPath = path.resolve(__dirname, '../tests/scripts/test-env.sh')
if (fs.existsSync(testEnvPath)) {
  const content = fs.readFileSync(testEnvPath, 'utf-8')
  for (const line of content.split('\n')) {
    const m = line.match(/^export\s+(\w+)="(.+)"/)
    if (m && !process.env[m[1]]) {
      process.env[m[1]] = m[2].replace(/\$\{(\w+)\}/g, (_, k) => process.env[k] ?? '')
    }
  }
}

export default defineConfig({
  testDir: '../tests/stage2/e2e',
  timeout: 10000,
  preserveOutput: 'never',
  fullyParallel: true,
  workers: 8,
  expect: {
    timeout: 5000
  },
  reporter: [
    ['list'],
    ['json', { outputFile: '../tests/stage2/results/stage2-results.json' }]
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
