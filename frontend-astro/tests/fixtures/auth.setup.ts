/**
 * Playwright Global Setup — Auth Session
 *
 * Logs in via the backend API and saves the session cookies as storageState
 * so that downstream "logged-in" projects can reuse the authenticated session.
 *
 * Required env vars:
 *   PLAYWRIGHT_TEST_EMAIL    — test account email
 *   PLAYWRIGHT_TEST_PASSWORD — test account password
 *
 * If either env var is missing the setup test is skipped (not failed),
 * which causes all dependent projects to be skipped as well.
 */
import { test as setup, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

/** Resolved path for the shared storageState JSON file. */
export const STORAGE_STATE = path.resolve(__dirname, '../.auth/session.json')

// Always ensure the storageState file exists (even as empty state)
// so the "logged-in" project can load it without error.
const authDir = path.resolve(__dirname, '../.auth')
if (!fs.existsSync(authDir)) {
  fs.mkdirSync(authDir, { recursive: true })
}
if (!fs.existsSync(STORAGE_STATE)) {
  fs.writeFileSync(STORAGE_STATE, JSON.stringify({ cookies: [], origins: [] }))
}

setup('authenticate via API', async ({ request }) => {
  const email = process.env.PLAYWRIGHT_TEST_EMAIL
  const password = process.env.PLAYWRIGHT_TEST_PASSWORD

  if (!email || !password) {
    setup.skip(true, 'PLAYWRIGHT_TEST_EMAIL / PLAYWRIGHT_TEST_PASSWORD not set — skipping auth setup')
    return
  }

  // POST /auth/login — the backend sets session cookies on the response
  const loginRes = await request.post('http://localhost:8088/auth/login', {
    data: { email, password },
  })

  expect(loginRes.ok(), `Login failed: ${loginRes.status()} ${loginRes.statusText()}`).toBeTruthy()

  // Persist cookies (+ localStorage / sessionStorage if any) to disk
  await request.storageState({ path: STORAGE_STATE })
})
