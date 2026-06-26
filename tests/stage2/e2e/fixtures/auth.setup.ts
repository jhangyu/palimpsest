/**
 * Playwright Global Setup — Auth Session
 *
 * Logs in via the frontend login page form and saves the browser session
 * (cookies + localStorage) as storageState so that downstream "logged-in"
 * projects can reuse the authenticated session.
 *
 * Required env vars:
 *   PLAYWRIGHT_TEST_EMAIL    — test account email
 *   PLAYWRIGHT_TEST_PASSWORD — test account password
 *
 * If either env var is missing the setup test throws a clear error
 * (NOT a silent skip) to prevent 130+ downstream failures from 401 redirects.
 * Source tests/scripts/test-env.sh before running to populate these vars.
 */
import { test as setup, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

/** Resolved path for the shared storageState JSON file. */
export const STORAGE_STATE = path.resolve(__dirname, '../.auth/session.json')

// Always ensure the storageState directory exists before the test runs.
const authDir = path.resolve(__dirname, '../.auth')
if (!fs.existsSync(authDir)) {
  fs.mkdirSync(authDir, { recursive: true })
}
if (!fs.existsSync(STORAGE_STATE)) {
  fs.writeFileSync(STORAGE_STATE, JSON.stringify({ cookies: [], origins: [] }))
}

setup('authenticate via login page', async ({ page }) => {
  const email = process.env.PLAYWRIGHT_TEST_EMAIL
  const password = process.env.PLAYWRIGHT_TEST_PASSWORD

  if (!email || !password) {
    throw new Error(
      'PLAYWRIGHT_TEST_EMAIL and PLAYWRIGHT_TEST_PASSWORD must be set. ' +
      'Source tests/scripts/test-env.sh first.'
    )
  }

  // Navigate to the frontend login page (baseURL = http://localhost:5174)
  await page.goto('/authentication/modern/login')

  // Wait for the login form to be visible
  await page.waitForSelector('#login-form', { timeout: 10000 })

  // Fill in credentials using the form field IDs from login.astro
  await page.fill('#email', email)
  await page.fill('#password', password)

  // Click the submit button
  await page.click('button[type="submit"]')

  // Wait for successful redirect to dashboard after login
  // In dev mode the frontend redirects to /dashboard (no /pages prefix)
  await page.waitForURL('**/dashboard', { timeout: 15000 })

  // Verify we landed on an authenticated page (not redirected back to login)
  expect(page.url()).not.toContain('/authentication/')

  // Persist the full browser session (cookies, localStorage, sessionStorage)
  // to disk so the "logged-in" project can reuse it.
  await page.context().storageState({ path: STORAGE_STATE })
})
