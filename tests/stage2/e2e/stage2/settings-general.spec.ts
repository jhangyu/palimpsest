/*
---
name: settings-general
description: "Stage 2 E2E: /settings — tab navigation (System Basics/Crawler Defaults/Maintenance/Notifications), HTML5 form validation, Notifications API GET/PUT integration, auth redirect"
stage: stage2
type: playwright
target:
  layer: frontend
  domain: settings-general
spec_doc: docs/test-specs/stage2/s2-06-settings-general.md
test_file: tests/stage2/e2e/stage2/settings-general.spec.ts
tests:
  - name: "6.01 Page loads with System Basics tab active by default"
    line: 19
    purpose: "System Basics panel is active and visible on initial page load"
  - name: "6.02 Nav-tree System Basics item is active on page load"
    line: 27
    purpose: "System Basics nav item has .active class on page load"
  - name: "6.03 Click Crawler Defaults tab switches panel"
    line: 32
    purpose: "Clicking Crawler Defaults nav item shows crawler-defaults panel"
  - name: "6.04 Click Maintenance tab switches panel"
    line: 41
    purpose: "Clicking Maintenance nav item shows maintenance panel"
  - name: "6.05 Click Notifications tab switches panel"
    line: 48
    purpose: "Clicking Notifications nav item shows notifications panel"
  - name: "6.06 Application Name required validation"
    line: 61
    purpose: "Submitting System Basics form with empty Application Name shows required error"
  - name: "6.07 Base URL required validation"
    line: 72
    purpose: "Submitting form with empty Base URL shows required validation error"
  - name: "6.08 Base URL format validation rejects invalid URL"
    line: 84
    purpose: "Non-URL value in Base URL field fails HTML5 url validation"
  - name: "6.09 Admin Email required validation"
    line: 97
    purpose: "Submitting form with empty Admin Email shows required validation error"
  - name: "6.10 Admin Email format validation rejects invalid email"
    line: 109
    purpose: "Non-email value in Admin Email field fails HTML5 email validation"
  - name: "6.11 Save Changes button exists with correct attributes"
    line: 122
    purpose: "Save Changes button is type='submit' and visible in System Basics panel"
  - name: "6.12 Valid form submission adds was-validated class without API call"
    line: 130
    purpose: "Valid form submit adds .was-validated class (placeholder form, no API wired)"
  - name: "6.13 All four number inputs visible with correct defaults"
    line: 153
    purpose: "Crawler Defaults panel shows all four number inputs with expected default values"
  - name: "6.14 Refresh Frequency min value validation (min=5)"
    line: 164
    purpose: "Refresh Frequency input below min=5 shows HTML5 range validation error"
  - name: "6.15 Auto-Repair Threshold min value validation (min=1)"
    line: 174
    purpose: "Auto-Repair Threshold input below min=1 shows HTML5 range validation error"
  - name: "6.16 Max Concurrent Crawls min value validation (min=1)"
    line: 184
    purpose: "Max Concurrent Crawls input below min=1 shows HTML5 range validation error"
  - name: "6.17 Crawl Timeout min value validation (min=10)"
    line: 194
    purpose: "Crawl Timeout input below min=10 shows HTML5 range validation error"
  - name: "6.18 Crawler Defaults Save Changes button exists"
    line: 204
    purpose: "Save Changes button visible in Crawler Defaults panel"
  - name: "6.19 Article Retention field visible with default value 30"
    line: 217
    purpose: "Article Retention input has default value of 30 in Maintenance panel"
  - name: "6.20 Logs Retention field visible with default value 14"
    line: 225
    purpose: "Logs Retention input has default value of 14 in Maintenance panel"
  - name: "6.21 Maintenance Save Changes button exists"
    line: 233
    purpose: "Save Changes button visible in Maintenance panel"
  - name: "6.22 Page load fetches preferences and updates toggles"
    line: 247
    purpose: "GET /settings/notifications populates notification toggle checkboxes"
  - name: "6.23 fail_crawl toggle defaults to checked"
    line: 275
    purpose: "fail_crawl notification toggle is checked by default"
  - name: "6.24 ai_reanalyze toggle defaults to checked"
    line: 295
    purpose: "ai_reanalyze notification toggle is checked by default"
  - name: "6.25 fail_access toggle defaults to checked"
    line: 315
    purpose: "fail_access notification toggle is checked by default"
  - name: "6.26 Uncheck fail_crawl and save sends PUT request"
    line: 335
    purpose: "Unchecking fail_crawl and saving sends PUT /settings/notifications with updated value"
  - name: "6.27 Save success shows \"Saved\" button text then reverts"
    line: 355
    purpose: "Save success changes button text to 'Saved' then reverts to 'Save Changes'"
  - name: "6.28 Saved preference persists after page reload"
    line: 371
    purpose: "Saved notification preference is reflected after page reload"
  - name: "6.29 Uncheck all toggles, save, reload — all remain unchecked"
    line: 387
    purpose: "All three toggles unchecked, saved, then confirmed unchecked after reload"
  - name: "6.30 Save Changes button is type=\"button\" (not submit)"
    line: 423
    purpose: "Notifications Save Changes button is type='button' (prevents default form submit)"
  - name: "6.31 Unauthenticated access to /settings redirects to login"
    line: 435
    purpose: "Cleared cookies navigating to /settings redirects to login page"
run:
  command: "cd frontend-astro && npx playwright test tests/stage2/e2e/stage2/settings-general.spec.ts"
  prerequisites:
    - "App running on http://localhost:5174"
---
*/
import { test, expect } from '@playwright/test'

// =============================================================================
// Tab Navigation
// =============================================================================
test.describe('Tab Navigation', () => {

  test('6.01 Page loads with System Basics tab active by default', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.locator('#system-section.show.active')).toBeVisible()
    await expect(page.locator('#crawler-section')).not.toHaveClass(/show/)
    await expect(page.locator('#maintenance-section')).not.toHaveClass(/show/)
    await expect(page.locator('#notifications-section')).not.toHaveClass(/show/)
  })

  test('6.02 Nav-tree System Basics item is active on page load', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.locator('.nav-tree .nav-item.active a[href="#system-section"]')).toBeVisible()
  })

  test('6.03 Click Crawler Defaults tab switches panel', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('a[href="#crawler-section"][data-bs-toggle="tab"]').click()
    await expect(page.locator('#crawler-section')).toHaveClass(/show/)
    await expect(page.locator('#crawler-section')).toHaveClass(/active/)
    await expect(page.locator('#system-section')).not.toHaveClass(/active/)
    await expect(page.locator('.nav-tree .nav-item.active').filter({ hasText: 'Crawler Defaults' })).toBeVisible()
  })

  test('6.04 Click Maintenance tab switches panel', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('a[href="#maintenance-section"][data-bs-toggle="tab"]').click()
    await expect(page.locator('#maintenance-section')).toHaveClass(/show/)
    await expect(page.locator('#maintenance-section')).toHaveClass(/active/)
  })

  test('6.05 Click Notifications tab switches panel', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()
    await expect(page.locator('#notifications-section')).toHaveClass(/show/)
    await expect(page.locator('#notifications-section')).toHaveClass(/active/)
  })
})

// =============================================================================
// System Basics — Form Validation
// =============================================================================
test.describe('System Basics — Form Validation', () => {

  test('6.06 Application Name required validation', async ({ page }) => {
    await page.goto('/settings')
    const input = page.locator('#system-form input[type="text"]')
    await input.clear()
    await page.locator('button[form="system-form"]').click()
    await expect(page.locator('#system-form')).toHaveClass(/was-validated/)
    await expect(page.locator('#system-form .invalid-feedback').first()).toBeVisible()
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test('6.07 Base URL required validation', async ({ page }) => {
    await page.goto('/settings')
    const input = page.locator('#system-form input[type="url"]')
    await input.clear()
    await page.locator('button[form="system-form"]').click()
    await expect(page.locator('#system-form')).toHaveClass(/was-validated/)
    // Scope to the URL field's invalid-feedback specifically to avoid strict-mode violation
    await expect(page.locator('#system-form .invalid-feedback').filter({ hasText: /URL/ })).toBeVisible()
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test('6.08 Base URL format validation rejects invalid URL', async ({ page }) => {
    await page.goto('/settings')
    const input = page.locator('#system-form input[type="url"]')
    await input.clear()
    await input.fill('not-a-url')
    await page.locator('button[form="system-form"]').click()
    await expect(page.locator('#system-form')).toHaveClass(/was-validated/)
    // Scope to the URL field's invalid-feedback specifically
    await expect(page.locator('#system-form .invalid-feedback').filter({ hasText: /URL/ })).toContainText('Please enter a valid URL')
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test('6.09 Admin Email required validation', async ({ page }) => {
    await page.goto('/settings')
    const input = page.locator('#system-form input[type="email"]')
    await input.clear()
    await page.locator('button[form="system-form"]').click()
    await expect(page.locator('#system-form')).toHaveClass(/was-validated/)
    // Scope to the email field's invalid-feedback specifically
    await expect(page.locator('#system-form .invalid-feedback').filter({ hasText: /email/ })).toBeVisible()
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test('6.10 Admin Email format validation rejects invalid email', async ({ page }) => {
    await page.goto('/settings')
    const input = page.locator('#system-form input[type="email"]')
    await input.clear()
    await input.fill('notanemail')
    await page.locator('button[form="system-form"]').click()
    await expect(page.locator('#system-form')).toHaveClass(/was-validated/)
    // Scope to the email field's invalid-feedback specifically
    await expect(page.locator('#system-form .invalid-feedback').filter({ hasText: /email/ })).toContainText('Please enter a valid email address')
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test('6.11 Save Changes button exists with correct attributes', async ({ page }) => {
    await page.goto('/settings')
    const btn = page.locator('#system-section .card-footer button[type="submit"][form="system-form"]')
    await expect(btn).toBeVisible()
    await expect(btn).toContainText('Save Changes')
    await expect(btn.locator('i.ri-save-3-line')).toBeVisible()
  })

  test('6.12 Valid form submission adds was-validated class without API call', async ({ page }) => {
    await page.goto('/settings')
    const requests: string[] = []
    page.on('request', req => requests.push(req.url()))

    // Fill valid values
    await page.locator('#system-form input[type="text"]').fill('My App')
    await page.locator('#system-form input[type="url"]').fill('https://example.com')
    await page.locator('#system-form input[type="email"]').fill('admin@example.com')
    await page.locator('button[form="system-form"]').click()

    await expect(page.locator('#system-form')).toHaveClass(/was-validated/)
    // Verify no fetch API call was made (placeholder UI only)
    const apiCalls = requests.filter(url => url.includes('/api/'))
    expect(apiCalls.filter(url => !url.includes('/users/me') && !url.includes('/auth/'))).toHaveLength(0)
  })
})

// =============================================================================
// Crawler Defaults — Form Validation
// =============================================================================
test.describe('Crawler Defaults — Form Validation', () => {

  test('6.13 All four number inputs visible with correct defaults', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('a[href="#crawler-section"][data-bs-toggle="tab"]').click()
    const inputs = page.locator('#crawler-form input[type="number"]')
    await expect(inputs).toHaveCount(4)
    await expect(inputs.nth(0)).toHaveValue('60')
    await expect(inputs.nth(1)).toHaveValue('3')
    await expect(inputs.nth(2)).toHaveValue('3')
    await expect(inputs.nth(3)).toHaveValue('30')
  })

  test('6.14 Refresh Frequency min value validation (min=5)', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('a[href="#crawler-section"][data-bs-toggle="tab"]').click()
    const input = page.locator('#crawler-form input[type="number"]').nth(0)
    await input.fill('4')
    await page.locator('button[form="crawler-form"]').click()
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test('6.15 Auto-Repair Threshold min value validation (min=1)', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('a[href="#crawler-section"][data-bs-toggle="tab"]').click()
    const input = page.locator('#crawler-form input[type="number"]').nth(1)
    await input.fill('0')
    await page.locator('button[form="crawler-form"]').click()
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test('6.16 Max Concurrent Crawls min value validation (min=1)', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('a[href="#crawler-section"][data-bs-toggle="tab"]').click()
    const input = page.locator('#crawler-form input[type="number"]').nth(2)
    await input.fill('0')
    await page.locator('button[form="crawler-form"]').click()
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test('6.17 Crawl Timeout min value validation (min=10)', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('a[href="#crawler-section"][data-bs-toggle="tab"]').click()
    const input = page.locator('#crawler-form input[type="number"]').nth(3)
    await input.fill('9')
    await page.locator('button[form="crawler-form"]').click()
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test('6.18 Crawler Defaults Save Changes button exists', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('a[href="#crawler-section"][data-bs-toggle="tab"]').click()
    const btn = page.locator('#crawler-section .card-footer button[type="submit"][form="crawler-form"]')
    await expect(btn).toBeVisible()
  })
})

// =============================================================================
// Maintenance — Form Fields
// =============================================================================
test.describe('Maintenance — Form Fields', () => {

  test('6.19 Article Retention field visible with default value 30', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('a[href="#maintenance-section"][data-bs-toggle="tab"]').click()
    const input = page.locator('#maintenance-form input[type="number"]').nth(0)
    await expect(input).toBeVisible()
    await expect(input).toHaveValue('30')
  })

  test('6.20 Logs Retention field visible with default value 14', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('a[href="#maintenance-section"][data-bs-toggle="tab"]').click()
    const input = page.locator('#maintenance-form input[type="number"]').nth(1)
    await expect(input).toBeVisible()
    await expect(input).toHaveValue('14')
  })

  test('6.21 Maintenance Save Changes button exists', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('a[href="#maintenance-section"][data-bs-toggle="tab"]').click()
    const btn = page.locator('#maintenance-section .card-footer button[type="submit"][form="maintenance-form"]')
    await expect(btn).toBeVisible()
  })
})

// =============================================================================
// Notifications — API Integration
// =============================================================================
test.describe('Notifications — API Integration', () => {
  test.describe.configure({ mode: 'serial' })

  test('6.22 Page load fetches preferences and updates toggles', async ({ page }) => {
    // Mock GET /users/me to return all notifications enabled (avoids backend state dependency)
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET' && !route.request().url().includes('/preferences')) {
        await route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'admin@example.com', username: 'admin',
            preferences: { notifications: { fail_crawl: true, ai_reanalyze: true, fail_access: true } }
          })
        })
      } else {
        await route.continue()
      }
    })
    // Set up waitForResponse BEFORE goto so it captures the fetch that fires on page load
    const responsePromise = page.waitForResponse(resp =>
      resp.url().includes('/users/me') && resp.request().method() === 'GET'
    )
    await page.goto('/settings')
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()
    await responsePromise
    await expect(page.locator('[data-notification-type="fail_crawl"]')).toBeVisible()
    await expect(page.locator('[data-notification-type="ai_reanalyze"]')).toBeVisible()
    await expect(page.locator('[data-notification-type="fail_access"]')).toBeVisible()
    await expect(page.locator('[data-notification-type="fail_crawl"]')).toBeChecked()
  })

  test('6.23 fail_crawl toggle defaults to checked', async ({ page }) => {
    // Mock GET /users/me to return all notifications enabled (avoids backend state dependency)
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET' && !route.request().url().includes('/preferences')) {
        await route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'admin@example.com', username: 'admin',
            preferences: { notifications: { fail_crawl: true, ai_reanalyze: true, fail_access: true } }
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/settings')
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()
    await expect(page.locator('#notif-fail-crawl')).toBeChecked()
  })

  test('6.24 ai_reanalyze toggle defaults to checked', async ({ page }) => {
    // Mock GET /users/me to return all notifications enabled (avoids backend state dependency)
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET' && !route.request().url().includes('/preferences')) {
        await route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'admin@example.com', username: 'admin',
            preferences: { notifications: { fail_crawl: true, ai_reanalyze: true, fail_access: true } }
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/settings')
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()
    await expect(page.locator('#notif-ai-reanalyze')).toBeChecked()
  })

  test('6.25 fail_access toggle defaults to checked', async ({ page }) => {
    // Mock GET /users/me to return all notifications enabled (avoids backend state dependency)
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET' && !route.request().url().includes('/preferences')) {
        await route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'admin@example.com', username: 'admin',
            preferences: { notifications: { fail_crawl: true, ai_reanalyze: true, fail_access: true } }
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/settings')
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()
    await expect(page.locator('#notif-fail-access')).toBeChecked()
  })

  test('6.26 Uncheck fail_crawl and save sends PUT request', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()
    await page.locator('#notif-fail-crawl').uncheck()

    // Set up GET promise BEFORE clicking save — the save sequence does GET then PUT,
    // both promises must be established before the click to capture all responses
    const getPromise = page.waitForResponse(resp =>
      resp.url().includes('/users/me') && !resp.url().includes('/preferences') && resp.request().method() === 'GET'
    )
    const putPromise = page.waitForResponse(resp =>
      resp.url().includes('/users/me/preferences') && resp.request().method() === 'PUT'
    )
    await page.locator('#btn-save-notifications').click()
    const putResponse = await putPromise
    expect(putResponse.status()).toBe(200)

    await getPromise
  })

  test('6.27 Save success shows "Saved" button text then reverts', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()

    const putPromise = page.waitForResponse(resp =>
      resp.url().includes('/users/me/preferences') && resp.request().method() === 'PUT' && resp.status() === 200
    )
    await page.locator('#btn-save-notifications').click()
    await putPromise

    await expect(page.locator('#btn-save-notifications')).toContainText('Saved')
    await expect(page.locator('#btn-save-notifications i.ri-check-line')).toBeVisible()
    // Wait for revert (2 seconds)
    await expect(page.locator('#btn-save-notifications')).toContainText('Save Changes', { timeout: 5000 })
  })

  test('6.28 Saved preference persists after page reload', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()
    await page.locator('#notif-fail-crawl').uncheck()

    const putPromise = page.waitForResponse(resp =>
      resp.url().includes('/users/me/preferences') && resp.request().method() === 'PUT'
    )
    await page.locator('#btn-save-notifications').click()
    await putPromise

    await page.reload()
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()
    await expect(page.locator('#notif-fail-crawl')).not.toBeChecked()
  })

  test('6.29 Uncheck all toggles, save, reload — all remain unchecked', async ({ page }) => {
    // Mock page-load GET /users/me exactly once (times: 1) so initial checkboxes are stable
    // (all true), then the save-handler GET and post-reload GET pass through to real backend
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET' && !route.request().url().includes('/preferences')) {
        await route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'admin@example.com', username: 'admin',
            preferences: { notifications: { fail_crawl: true, ai_reanalyze: true, fail_access: true } }
          })
        })
      } else {
        await route.continue()
      }
    }, { times: 1 })
    await page.goto('/settings')
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()

    await page.locator('#notif-fail-crawl').uncheck()
    await page.locator('#notif-ai-reanalyze').uncheck()
    await page.locator('#notif-fail-access').uncheck()

    const putPromise = page.waitForResponse(resp =>
      resp.url().includes('/users/me/preferences') && resp.request().method() === 'PUT'
    )
    await page.locator('#btn-save-notifications').click()
    await putPromise

    await page.reload()
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()
    await expect(page.locator('#notif-fail-crawl')).not.toBeChecked()
    await expect(page.locator('#notif-ai-reanalyze')).not.toBeChecked()
    await expect(page.locator('#notif-fail-access')).not.toBeChecked()
  })

  test('6.30 Save Changes button is type="button" (not submit)', async ({ page }) => {
    await page.goto('/settings')
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()
    await expect(page.locator('#btn-save-notifications')).toHaveAttribute('type', 'button')
  })
})

// =============================================================================
// Authentication Guard
// =============================================================================
test.describe('Authentication Guard', () => {

  test('6.31 Unauthenticated access to /settings redirects to login', async ({ page }) => {
    // Clear cookies to simulate unauthenticated state
    await page.context().clearCookies()
    await page.goto('/settings')
    await page.waitForURL('**/login**', { timeout: 15000 })
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })
})
