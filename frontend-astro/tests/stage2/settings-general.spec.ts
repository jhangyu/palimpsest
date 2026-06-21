/**
 * S2-06: Settings General — Playwright Tests
 * Spec: docs/test-specs/s2-06-settings-general.md
 *
 * Covers: /settings page — Tab navigation (System Basics, Crawler Defaults,
 * Maintenance, Notifications), HTML5 form validation for placeholder forms,
 * Notifications API integration (GET/PUT), and auth redirect.
 *
 * Tests requiring authentication are marked test.skip until session fixture lands.
 * Run: npx playwright test tests/stage2/settings-general.spec.ts
 */
import { test, expect } from '@playwright/test'

// =============================================================================
// Tab Navigation
// =============================================================================
test.describe('Tab Navigation', () => {

  test.skip('6.01 Page loads with System Basics tab active by default', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    await expect(page.locator('#system-section.show.active')).toBeVisible()
    await expect(page.locator('#crawler-section')).not.toHaveClass(/show/)
    await expect(page.locator('#maintenance-section')).not.toHaveClass(/show/)
    await expect(page.locator('#notifications-section')).not.toHaveClass(/show/)
  })

  test.skip('6.02 Nav-tree System Basics item is active on page load', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    await expect(page.locator('.nav-tree .nav-item.active a[href="#system-section"]')).toBeVisible()
  })

  test.skip('6.03 Click Crawler Defaults tab switches panel', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    await page.locator('a[href="#crawler-section"][data-bs-toggle="tab"]').click()
    await expect(page.locator('#crawler-section')).toHaveClass(/show/)
    await expect(page.locator('#crawler-section')).toHaveClass(/active/)
    await expect(page.locator('#system-section')).not.toHaveClass(/active/)
    await expect(page.locator('.nav-tree .nav-item.active')).toBeVisible()
  })

  test.skip('6.04 Click Maintenance tab switches panel', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    await page.locator('a[href="#maintenance-section"][data-bs-toggle="tab"]').click()
    await expect(page.locator('#maintenance-section')).toHaveClass(/show/)
    await expect(page.locator('#maintenance-section')).toHaveClass(/active/)
  })

  test.skip('6.05 Click Notifications tab switches panel', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('6.06 Application Name required validation', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    const input = page.locator('#system-form input[type="text"]')
    await input.clear()
    await page.locator('button[form="system-form"]').click()
    await expect(page.locator('#system-form')).toHaveClass(/was-validated/)
    await expect(page.locator('#system-form .invalid-feedback').first()).toBeVisible()
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test.skip('6.07 Base URL required validation', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    const input = page.locator('#system-form input[type="url"]')
    await input.clear()
    await page.locator('button[form="system-form"]').click()
    await expect(page.locator('#system-form')).toHaveClass(/was-validated/)
    await expect(page.locator('#system-form .invalid-feedback').first()).toBeVisible()
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test.skip('6.08 Base URL format validation rejects invalid URL', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    const input = page.locator('#system-form input[type="url"]')
    await input.clear()
    await input.fill('not-a-url')
    await page.locator('button[form="system-form"]').click()
    await expect(page.locator('#system-form')).toHaveClass(/was-validated/)
    await expect(page.locator('#system-form .invalid-feedback').first()).toContainText('Please enter a valid URL')
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test.skip('6.09 Admin Email required validation', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    const input = page.locator('#system-form input[type="email"]')
    await input.clear()
    await page.locator('button[form="system-form"]').click()
    await expect(page.locator('#system-form')).toHaveClass(/was-validated/)
    await expect(page.locator('#system-form .invalid-feedback').first()).toBeVisible()
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test.skip('6.10 Admin Email format validation rejects invalid email', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    const input = page.locator('#system-form input[type="email"]')
    await input.clear()
    await input.fill('notanemail')
    await page.locator('button[form="system-form"]').click()
    await expect(page.locator('#system-form')).toHaveClass(/was-validated/)
    await expect(page.locator('#system-form .invalid-feedback').first()).toContainText('Please enter a valid email address')
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test.skip('6.11 Save Changes button exists with correct attributes', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    const btn = page.locator('#system-section .card-footer button[type="submit"][form="system-form"]')
    await expect(btn).toBeVisible()
    await expect(btn).toContainText('Save Changes')
    await expect(btn.locator('i.ri-save-3-line')).toBeVisible()
  })

  test.skip('6.12 Valid form submission adds was-validated class without API call', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('6.13 All four number inputs visible with correct defaults', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    await page.locator('a[href="#crawler-section"][data-bs-toggle="tab"]').click()
    const inputs = page.locator('#crawler-form input[type="number"]')
    await expect(inputs).toHaveCount(4)
    await expect(inputs.nth(0)).toHaveValue('60')
    await expect(inputs.nth(1)).toHaveValue('3')
    await expect(inputs.nth(2)).toHaveValue('3')
    await expect(inputs.nth(3)).toHaveValue('30')
  })

  test.skip('6.14 Refresh Frequency min value validation (min=5)', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    await page.locator('a[href="#crawler-section"][data-bs-toggle="tab"]').click()
    const input = page.locator('#crawler-form input[type="number"]').nth(0)
    await input.fill('4')
    await page.locator('button[form="crawler-form"]').click()
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test.skip('6.15 Auto-Repair Threshold min value validation (min=1)', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    await page.locator('a[href="#crawler-section"][data-bs-toggle="tab"]').click()
    const input = page.locator('#crawler-form input[type="number"]').nth(1)
    await input.fill('0')
    await page.locator('button[form="crawler-form"]').click()
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test.skip('6.16 Max Concurrent Crawls min value validation (min=1)', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    await page.locator('a[href="#crawler-section"][data-bs-toggle="tab"]').click()
    const input = page.locator('#crawler-form input[type="number"]').nth(2)
    await input.fill('0')
    await page.locator('button[form="crawler-form"]').click()
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test.skip('6.17 Crawl Timeout min value validation (min=10)', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    await page.locator('a[href="#crawler-section"][data-bs-toggle="tab"]').click()
    const input = page.locator('#crawler-form input[type="number"]').nth(3)
    await input.fill('9')
    await page.locator('button[form="crawler-form"]').click()
    const isValid = await input.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test.skip('6.18 Crawler Defaults Save Changes button exists', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('6.19 Article Retention field visible with default value 30', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    await page.locator('a[href="#maintenance-section"][data-bs-toggle="tab"]').click()
    const input = page.locator('#maintenance-form input[type="number"]').nth(0)
    await expect(input).toBeVisible()
    await expect(input).toHaveValue('30')
  })

  test.skip('6.20 Logs Retention field visible with default value 14', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    await page.locator('a[href="#maintenance-section"][data-bs-toggle="tab"]').click()
    const input = page.locator('#maintenance-form input[type="number"]').nth(1)
    await expect(input).toBeVisible()
    await expect(input).toHaveValue('14')
  })

  test.skip('6.21 Maintenance Save Changes button exists', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('6.22 Page load fetches preferences and updates toggles', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    const responsePromise = page.waitForResponse(resp =>
      resp.url().includes('/users/me') && resp.request().method() === 'GET'
    )
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()
    await responsePromise
    await expect(page.locator('[data-notification-type="fail_crawl"]')).toBeVisible()
    await expect(page.locator('[data-notification-type="ai_reanalyze"]')).toBeVisible()
    await expect(page.locator('[data-notification-type="fail_access"]')).toBeVisible()
    await expect(page.locator('[data-notification-type="fail_crawl"]')).toBeChecked()
  })

  test.skip('6.23 fail_crawl toggle defaults to checked', async ({ page }) => {
    // TODO: requires auth session fixture (user with empty preferences)
    await page.goto('/settings')
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()
    await expect(page.locator('#notif-fail-crawl')).toBeChecked()
  })

  test.skip('6.24 ai_reanalyze toggle defaults to checked', async ({ page }) => {
    // TODO: requires auth session fixture (user with empty preferences)
    await page.goto('/settings')
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()
    await expect(page.locator('#notif-ai-reanalyze')).toBeChecked()
  })

  test.skip('6.25 fail_access toggle defaults to checked', async ({ page }) => {
    // TODO: requires auth session fixture (user with empty preferences)
    await page.goto('/settings')
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()
    await expect(page.locator('#notif-fail-access')).toBeChecked()
  })

  test.skip('6.26 Uncheck fail_crawl and save sends PUT request', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()
    await page.locator('#notif-fail-crawl').uncheck()

    const putPromise = page.waitForResponse(resp =>
      resp.url().includes('/users/me/preferences') && resp.request().method() === 'PUT'
    )
    await page.locator('#btn-save-notifications').click()
    const putResponse = await putPromise
    expect(putResponse.status()).toBe(200)

    const getPromise = page.waitForResponse(resp =>
      resp.url().includes('/users/me') && resp.request().method() === 'GET'
    )
    await getPromise
  })

  test.skip('6.27 Save success shows "Saved" button text then reverts', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('6.28 Saved preference persists after page reload', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('6.29 Uncheck all toggles, save, reload — all remain unchecked', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('6.30 Save Changes button is type="button" (not submit)', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings')
    await page.locator('a[href="#notifications-section"][data-bs-toggle="tab"]').click()
    await expect(page.locator('#btn-save-notifications')).toHaveAttribute('type', 'button')
  })
})

// =============================================================================
// Authentication Guard
// =============================================================================
test.describe('Authentication Guard', () => {

  test.skip('6.31 Unauthenticated access to /settings redirects to login', async ({ page }) => {
    // TODO: requires verifying redirect behavior when NOT logged in
    await page.goto('/settings')
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })
})
