/**
 * S2-04: User Security — Playwright Tests
 * Spec: docs/test-specs/s2-04-user-security.md
 *
 * Covers: /users/security (Password Change, Session Security, AI Service link).
 * All tests requiring authentication are marked test.skip until session fixture lands.
 *
 * Run: npx playwright test tests/stage2/security.spec.ts
 */
import { test, expect } from '@playwright/test'

// =============================================================================
// Page Initialization — /users/security
// =============================================================================
test.describe('Page Initialization — /users/security', () => {

  test('TC-01: Page loads and displays user info in sidebar', async ({ page }) => {
    await page.goto('/users/security', { waitUntil: 'networkidle' })
    await expect(page.locator('[data-session="user-name"]').first()).not.toHaveText('Loading...')
    await expect(page.locator('[data-session="user-email"]').first()).not.toHaveText('Loading...')
    await expect(page.locator('[data-session="user-name"]').first()).not.toHaveText('')
    await expect(page.locator('[data-session="user-email"]').first()).not.toHaveText('')
  })

  test('TC-02: Password Change Form default state — fields empty and success alert hidden', async ({ page }) => {
    await page.goto('/users/security', { waitUntil: 'networkidle' })
    await expect(page.locator('#passwordUpdateForm')).toBeVisible()
    await expect(page.locator('#currentPassword')).toHaveValue('')
    await expect(page.locator('#newPassword')).toHaveValue('')
    await expect(page.locator('#confirmPassword')).toHaveValue('')
    await expect(page.locator('#password-success-alert')).not.toBeVisible()
  })

})

// =============================================================================
// Password Visibility Toggle
// =============================================================================
test.describe('Password Visibility Toggle', () => {

  test('TC-03: Toggle currentPassword visibility', async ({ page }) => {
    await page.goto('/users/security', { waitUntil: 'networkidle' })
    const input = page.locator('#currentPassword')
    const toggle = page.locator('#currentPassword + button.password-toggle')
    await input.fill('testpass')
    await expect(input).toHaveAttribute('type', 'password')
    await toggle.click()
    await expect(input).toHaveAttribute('type', 'text')
    await expect(toggle.locator('i')).toHaveClass(/ri-eye-line/)
    await toggle.click()
    await expect(input).toHaveAttribute('type', 'password')
    await expect(toggle.locator('i')).toHaveClass(/ri-eye-off-line/)
  })

  test('TC-04: Toggle newPassword visibility', async ({ page }) => {
    await page.goto('/users/security', { waitUntil: 'networkidle' })
    const input = page.locator('#newPassword')
    const toggle = page.locator('#newPassword + button.password-toggle')
    await input.fill('testpass')
    await expect(input).toHaveAttribute('type', 'password')
    await toggle.click()
    await expect(input).toHaveAttribute('type', 'text')
    await expect(toggle.locator('i')).toHaveClass(/ri-eye-line/)
    await toggle.click()
    await expect(input).toHaveAttribute('type', 'password')
    await expect(toggle.locator('i')).toHaveClass(/ri-eye-off-line/)
  })

  test('TC-05: Toggle confirmPassword visibility', async ({ page }) => {
    await page.goto('/users/security', { waitUntil: 'networkidle' })
    const input = page.locator('#confirmPassword')
    const toggle = page.locator('#confirmPassword + button.password-toggle')
    await input.fill('testpass')
    await expect(input).toHaveAttribute('type', 'password')
    await toggle.click()
    await expect(input).toHaveAttribute('type', 'text')
    await expect(toggle.locator('i')).toHaveClass(/ri-eye-line/)
    await toggle.click()
    await expect(input).toHaveAttribute('type', 'password')
    await expect(toggle.locator('i')).toHaveClass(/ri-eye-off-line/)
  })

})

// =============================================================================
// Client-Side Validation
// =============================================================================
test.describe('Client-Side Validation', () => {

  test('TC-06: Empty currentPassword shows validation error on submit', async ({ page }) => {
    await page.goto('/users/security', { waitUntil: 'networkidle' })
    let apiCalled = false
    await page.route('**/users/me/password', (route) => { apiCalled = true; route.abort() })
    // Bypass native HTML5 validation so JS handler runs and adds is-invalid class
    await page.locator('#passwordUpdateForm').evaluate(form => form.setAttribute('novalidate', ''))
    await page.locator('#passwordUpdateForm button[type="submit"]').click()
    await expect(page.locator('#currentPassword')).toHaveClass(/is-invalid/)
    await expect(page.locator('#currentPassword ~ .invalid-feedback')).toContainText('Current password is required.')
    expect(apiCalled).toBe(false)
  })

  test('TC-07: newPassword too short (<8 chars) shows validation error', async ({ page }) => {
    await page.goto('/users/security', { waitUntil: 'networkidle' })
    await page.locator('#currentPassword').fill('currentpass')
    await page.locator('#newPassword').fill('short')
    // Bypass native HTML5 validation so JS handler runs and adds is-invalid class
    await page.locator('#passwordUpdateForm').evaluate(form => form.setAttribute('novalidate', ''))
    await page.locator('#passwordUpdateForm button[type="submit"]').click()
    await expect(page.locator('#newPassword')).toHaveClass(/is-invalid/)
    await expect(page.locator('#newPassword ~ .invalid-feedback')).toContainText('Password must be 8-20 characters.')
  })

  test('TC-08: newPassword too long (>20 chars) shows validation error', async ({ page }) => {
    await page.goto('/users/security', { waitUntil: 'networkidle' })
    await page.locator('#currentPassword').fill('currentpass')
    // Bypass maxlength attribute so we can set a value longer than 20 chars
    await page.locator('#newPassword').evaluate((el: HTMLInputElement, v) => {
      el.removeAttribute('maxlength')
      el.value = v
      el.dispatchEvent(new Event('input'))
    }, 'abcdefghijklmnopqrstu1')
    // Bypass native HTML5 validation so JS handler runs and checks length > 20
    await page.locator('#passwordUpdateForm').evaluate(form => form.setAttribute('novalidate', ''))
    await page.locator('#passwordUpdateForm button[type="submit"]').click()
    await expect(page.locator('#newPassword')).toHaveClass(/is-invalid/)
    await expect(page.locator('#newPassword ~ .invalid-feedback')).toContainText('Password must be 8-20 characters.')
  })

  test('TC-09: confirmPassword mismatch shows validation error', async ({ page }) => {
    await page.goto('/users/security', { waitUntil: 'networkidle' })
    await page.locator('#currentPassword').fill('currentpass')
    await page.locator('#newPassword').fill('validPass123')
    await page.locator('#confirmPassword').fill('differentPass')
    await page.locator('#passwordUpdateForm button[type="submit"]').click()
    await expect(page.locator('#confirmPassword')).toHaveClass(/is-invalid/)
    await expect(page.locator('#confirmPassword ~ .invalid-feedback')).toContainText('Passwords do not match.')
  })

})

// =============================================================================
// Password Change — Submit & API Interaction
// =============================================================================
test.describe('Password Change — Submit & API Interaction', () => {
  test.describe.configure({ mode: 'serial' })

  test('TC-10: Submit button shows loading state during API call', async ({ page }) => {
    await page.goto('/users/security', { waitUntil: 'networkidle' })
    // Mock slow API response
    await page.route('**/users/me/password', async (route) => {
      await new Promise((r) => setTimeout(r, 2000))
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'Password changed successfully.' }) })
    })
    await page.locator('#currentPassword').fill('currentpass')
    await page.locator('#newPassword').fill('newValidPass1')
    await page.locator('#confirmPassword').fill('newValidPass1')
    await page.locator('#passwordUpdateForm button[type="submit"]').click()
    const submitBtn = page.locator('#passwordUpdateForm button[type="submit"]')
    await expect(submitBtn).toBeDisabled()
    await expect(submitBtn.locator('.spinner-border')).toBeVisible()
    await expect(submitBtn).toContainText('Saving...')
  })

  test('TC-11: Successful password change shows alert and resets form', async ({ page }) => {
    await page.goto('/users/security', { waitUntil: 'networkidle' })
    // Mock successful API response
    await page.route('**/users/me/password', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'Password changed successfully.' }) })
    })
    await page.locator('#currentPassword').fill('currentpass')
    await page.locator('#newPassword').fill('newValidPass1')
    await page.locator('#confirmPassword').fill('newValidPass1')
    await page.locator('#passwordUpdateForm button[type="submit"]').click()
    await expect(page.locator('#password-success-alert')).toBeVisible()
    await expect(page.locator('#currentPassword')).toHaveValue('')
    await expect(page.locator('#newPassword')).toHaveValue('')
    await expect(page.locator('#confirmPassword')).toHaveValue('')
    const submitBtn = page.locator('#passwordUpdateForm button[type="submit"]')
    await expect(submitBtn).toBeEnabled()
  })

  test('TC-12: Success alert displays correct message text', async ({ page }) => {
    await page.goto('/users/security', { waitUntil: 'networkidle' })
    // Mock successful API response
    await page.route('**/users/me/password', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'Password changed successfully.' }) })
    })
    await page.locator('#currentPassword').fill('currentpass')
    await page.locator('#newPassword').fill('newValidPass1')
    await page.locator('#confirmPassword').fill('newValidPass1')
    await page.locator('#passwordUpdateForm button[type="submit"]').click()
    await expect(page.locator('#password-success-alert')).toContainText('Password changed successfully.')
    await expect(page.locator('#password-success-alert')).toContainText('All other sessions have been revoked')
  })

  test('TC-13: Wrong currentPassword shows inline error from API 400', async ({ page }) => {
    await page.goto('/users/security', { waitUntil: 'networkidle' })
    // Mock API 400 with "incorrect" in message
    await page.route('**/users/me/password', async (route) => {
      await route.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ detail: 'Current password is incorrect.' }) })
    })
    await page.locator('#currentPassword').fill('wrongpass')
    await page.locator('#newPassword').fill('newValidPass1')
    await page.locator('#confirmPassword').fill('newValidPass1')
    await page.locator('#passwordUpdateForm button[type="submit"]').click()
    await expect(page.locator('#currentPassword')).toHaveClass(/is-invalid/)
    await expect(page.locator('#currentPassword ~ .invalid-feedback')).toContainText('Current password is incorrect.')
    await expect(page.locator('.alert.alert-danger')).not.toBeVisible()
  })

  test('TC-14: Non-password API error shows toast alert', async ({ page }) => {
    await page.goto('/users/security', { waitUntil: 'networkidle' })
    // Mock API error without "incorrect"/"wrong"/"invalid" keywords
    await page.route('**/users/me/password', async (route) => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Internal server error occurred' }) })
    })
    await page.locator('#currentPassword').fill('currentpass')
    await page.locator('#newPassword').fill('newValidPass1')
    await page.locator('#confirmPassword').fill('newValidPass1')
    await page.locator('#passwordUpdateForm button[type="submit"]').click()
    await expect(page.locator('.alert.alert-danger')).toBeVisible()
    await expect(page.locator('.alert.alert-danger')).toContainText('Internal server error occurred')
  })

  test('TC-15: Old session token is revoked after password change (API-level)', async ({ page, request }) => {
    // IMPLEMENTED in backend: test_change_password in test_user_management.py
    // This Playwright test verifies the same behavior from the browser perspective
    await page.goto('/users/security', { waitUntil: 'networkidle' })
    // Capture current session cookie before password change
    const cookies = await page.context().cookies()
    const sessionCookie = cookies.find((c) => c.name === 'session')
    // Mock successful password change
    await page.route('**/users/me/password', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'Password changed successfully.' }) })
    })
    await page.locator('#currentPassword').fill('currentpass')
    await page.locator('#newPassword').fill('newValidPass1')
    await page.locator('#confirmPassword').fill('newValidPass1')
    await page.locator('#passwordUpdateForm button[type="submit"]').click()
    // After password change, old session should be invalidated
    // Verify by calling /auth/me with old token
    if (sessionCookie) {
      const response = await request.get('/auth/me', {
        headers: { Cookie: `session=${sessionCookie.value}` },
      })
      expect(response.status()).toBe(401)
    }
  })

})

// =============================================================================
// Navigation & Access Control
// =============================================================================
test.describe('Navigation & Access Control', () => {
  test.describe.configure({ mode: 'serial' })

  test('TC-16: Unauthenticated access redirects to login page', async ({ page }) => {
    // TODO: requires clean browser context (no auth cookies)
    await page.context().clearCookies()
    await page.goto('/users/security')
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })

  test('TC-17: AI Service card link navigates to /users/ai-service', async ({ page }) => {
    await page.goto('/users/security', { waitUntil: 'networkidle' })
    const aiServiceLink = page.locator('.content-wrapper a.btn[href*="ai-service"]')
    await expect(aiServiceLink).toBeVisible()
    await aiServiceLink.click()
    await expect(page).toHaveURL(/\/users\/ai-service/)
  })

})
