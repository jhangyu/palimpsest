/**
 * S2-03: User Profile — Playwright Tests
 * Spec: docs/test-specs/s2-03-user-profile.md
 *
 * Covers: /users/profile (User Profile page) and /users/edit?id={userId} (Edit User admin page).
 * All tests requiring authentication are marked test.skip until session fixture lands.
 *
 * Run: npx playwright test tests/stage2/profile.spec.ts
 */
import { test, expect } from '@playwright/test'

// =============================================================================
// Page Initialization — /users/profile
// =============================================================================
test.describe('Page Initialization — /users/profile', () => {

  test.skip('P-01: Page loads profile from API and populates form fields', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await expect(page.locator('#profile-full-name')).not.toHaveValue('')
    await expect(page.locator('#profile-email')).not.toHaveValue('')
    await expect(page.locator('#profile-username')).not.toHaveValue('')
    await expect(page.locator('[data-session="user-name"]')).not.toHaveText('Loading...')
  })

  test.skip('P-02: Pending email banner visible when pending_email exists', async ({ page }) => {
    // TODO: requires auth session fixture + user with pending_email set
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await expect(page.locator('#pending-email-banner')).toBeVisible()
    await expect(page.locator('#pending-email-text')).toBeVisible()
    await expect(page.locator('#pending-email-text')).not.toHaveText('')
  })

  test.skip('P-03: Pending email banner hidden when no pending_email', async ({ page }) => {
    // TODO: requires auth session fixture + user without pending_email
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await expect(page.locator('#pending-email-banner')).not.toBeVisible()
  })

  test.skip('P-04: Avatar image visible when avatar_source is upload or gravatar', async ({ page }) => {
    // TODO: requires auth session fixture + user with uploaded avatar
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await expect(page.locator('#profile-avatar-img')).not.toHaveClass(/d-none/)
    await expect(page.locator('#avatar-placeholder')).toHaveClass(/d-none/)
  })

  test.skip('P-05: Placeholder icon visible when avatar_source is none', async ({ page }) => {
    // TODO: requires auth session fixture + user without avatar
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await expect(page.locator('#avatar-placeholder')).toBeVisible()
    await expect(page.locator('#profile-avatar-img')).toHaveClass(/d-none/)
  })

  test.skip('P-06: Avatar source badge shows correct text', async ({ page }) => {
    // TODO: requires auth session fixture
    // source=none → "No avatar"; source=upload → "Uploaded photo"; source=gravatar → "Gravatar"
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await expect(page.locator('#avatar-source-badge')).toContainText(/No avatar|Uploaded photo|Gravatar/)
  })

  test.skip('P-07: Gravatar toggle unchecked by default for new user', async ({ page }) => {
    // TODO: requires auth session fixture + user with avatar_source=none
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await expect(page.locator('#gravatar-toggle')).not.toBeChecked()
  })

})

// =============================================================================
// Display Name — #full-name-form
// =============================================================================
test.describe('Display Name — #full-name-form', () => {

  test.skip('P-08: Save full name successfully', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-full-name').fill('New Display Name')
    await page.locator('#full-name-form button[type="submit"]').click()
    // Button should enter loading state; PUT /users/me called; toast "Full name updated." appears
    await expect(page.locator('#full-name-form button[type="submit"]')).toBeDisabled()
    await expect(page.locator('.toast-body, .toast')).toContainText('Full name updated.')
  })

  test.skip('P-09: Save empty full name allowed', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-full-name').fill('')
    await page.locator('#full-name-form button[type="submit"]').click()
    // PUT /users/me with {full_name: ""} should succeed; toast appears
    await expect(page.locator('.toast-body, .toast')).toBeVisible()
  })

})

// =============================================================================
// Email Address — #email-change-form
// =============================================================================
test.describe('Email Address — #email-change-form', () => {

  test.skip('P-10: Submit email change shows pending verification banner', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-email').fill('newemail@example.com')
    await page.locator('#profile-email-password').fill('currentpassword')
    await page.locator('#email-change-form button[type="submit"]').click()
    // PUT /users/me/email called; toast "Verification email sent..."; banner visible; password cleared
    await expect(page.locator('#pending-email-banner')).toBeVisible()
    await expect(page.locator('#profile-email-password')).toHaveValue('')
  })

  test.skip('P-11: Invalid email format shows field error', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-email').fill('invalidemail')
    await page.locator('#email-change-form button[type="submit"]').click()
    await expect(page.locator('#profile-email')).toHaveClass(/is-invalid/)
    await expect(page.locator('#email-change-form .invalid-feedback')).toBeVisible()
  })

  test.skip('P-12: Missing password shows field error', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-email').fill('valid@example.com')
    // Leave password empty
    await page.locator('#email-change-form button[type="submit"]').click()
    await expect(page.locator('#profile-email-password')).toHaveClass(/is-invalid/)
  })

  test.skip('P-13: Same email as current shows field error', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    const currentEmail = await page.locator('#profile-email').inputValue()
    await page.locator('#profile-email').fill(currentEmail)
    await page.locator('#email-change-form button[type="submit"]').click()
    await expect(page.locator('#profile-email')).toHaveClass(/is-invalid/)
    // Hint: "same as current"
    await expect(page.locator('#email-change-form .invalid-feedback')).toContainText(/same as current/i)
  })

  test.skip('P-14: Wrong password API error shown on field', async ({ page }) => {
    // TODO: requires auth session fixture + API mock returning 401/400
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-email').fill('newemail@example.com')
    await page.locator('#profile-email-password').fill('wrongpassword')
    await page.locator('#email-change-form button[type="submit"]').click()
    // Error message displayed in field or toast
    await expect(page.locator('#email-change-form .invalid-feedback')).toBeVisible()
  })

  test.skip('P-15: Pending banner disappears after email verification', async ({ page }) => {
    // TODO: requires auth session fixture + simulate verify-email endpoint call
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    // After verification, reload and check banner is hidden
    await expect(page.locator('#pending-email-banner')).not.toBeVisible()
    await expect(page.locator('#profile-email')).toHaveValue('newemail@example.com')
  })

})

// =============================================================================
// Username — #username-change-form
// =============================================================================
test.describe('Username — #username-change-form', () => {

  test.skip('P-16: Save valid lowercase username successfully', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-username').fill('validname')
    await page.locator('#username-change-form button[type="submit"]').click()
    // PUT /users/me/username called; toast "Username updated successfully."
    await expect(page.locator('.toast-body, .toast')).toContainText('Username updated successfully.')
  })

  test.skip('P-17: Username with uppercase characters shows field error', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-username').fill('Admin')
    await page.locator('#username-change-form button[type="submit"]').click()
    await expect(page.locator('#profile-username')).toHaveClass(/is-invalid/)
    await expect(page.locator('#username-change-form .invalid-feedback')).toBeVisible()
  })

  test.skip('P-18: Username with digits or special chars shows field error', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-username').fill('user123')
    await page.locator('#username-change-form button[type="submit"]').click()
    await expect(page.locator('#profile-username')).toHaveClass(/is-invalid/)
    await expect(page.locator('#username-change-form .invalid-feedback')).toBeVisible()
  })

  test.skip('P-19: Reserved username shows API error', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-username').fill('admin')
    await page.locator('#username-change-form button[type="submit"]').click()
    // API returns 4xx; field shows "reserved username" error
    await expect(page.locator('#profile-username')).toHaveClass(/is-invalid/)
    await expect(page.locator('#username-change-form .invalid-feedback')).toContainText(/reserved/i)
  })

  test.skip('P-20: Duplicate username shows conflict error', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-username').fill('existinguser')
    await page.locator('#username-change-form button[type="submit"]').click()
    // API returns 409; field shows "already taken" error
    await expect(page.locator('#profile-username')).toHaveClass(/is-invalid/)
    await expect(page.locator('#username-change-form .invalid-feedback')).toContainText(/already taken/i)
  })

})

// =============================================================================
// Profile Photo — Avatar Upload
// =============================================================================
test.describe('Profile Photo — Avatar Upload', () => {

  test.skip('P-21: Upload button triggers file input', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    const fileInput = page.locator('#avatar-file-input')
    await expect(fileInput).toHaveAttribute('accept', 'image/jpeg,image/png,image/webp')
    // Clicking #avatar-upload-btn should trigger #avatar-file-input click
    await page.locator('#avatar-upload-btn').click()
  })

  test.skip('P-22: Upload valid JPEG shows avatar image and hides placeholder', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    // Upload 1KB JPEG via setInputFiles
    await page.locator('#avatar-file-input').setInputFiles({
      name: 'avatar.jpg',
      mimeType: 'image/jpeg',
      buffer: Buffer.alloc(1024),
    })
    // PUT /users/me/avatar called; avatar visible; placeholder hidden; badge = "Uploaded photo"
    await expect(page.locator('#profile-avatar-img')).not.toHaveClass(/d-none/)
    await expect(page.locator('#avatar-placeholder')).toHaveClass(/d-none/)
    await expect(page.locator('#avatar-source-badge')).toHaveText('Uploaded photo')
  })

  test.skip('P-23: Upload SVG shows format error toast', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#avatar-file-input').setInputFiles({
      name: 'image.svg',
      mimeType: 'image/svg+xml',
      buffer: Buffer.from('<svg></svg>'),
    })
    // toast "Only JPEG, PNG, or WebP images are allowed."; no API call; file input cleared
    await expect(page.locator('.toast-body, .toast')).toContainText('Only JPEG, PNG, or WebP images are allowed.')
    await expect(page.locator('#avatar-file-input')).toHaveValue('')
  })

  test.skip('P-24: Upload oversized image shows size error toast', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    // Upload >512KB PNG
    await page.locator('#avatar-file-input').setInputFiles({
      name: 'large.png',
      mimeType: 'image/png',
      buffer: Buffer.alloc(600 * 1024),
    })
    // toast "Image must be 512 KB or smaller."; no API call; file input cleared
    await expect(page.locator('.toast-body, .toast')).toContainText('Image must be 512 KB or smaller.')
    await expect(page.locator('#avatar-file-input')).toHaveValue('')
  })

})

// =============================================================================
// Profile Photo — Avatar Delete
// =============================================================================
test.describe('Profile Photo — Avatar Delete', () => {

  test.skip('P-25: Delete avatar restores placeholder and hides image', async ({ page }) => {
    // TODO: requires auth session fixture + user with uploaded avatar
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    page.on('dialog', dialog => dialog.accept())
    await page.locator('#avatar-delete-btn').click()
    // DELETE /users/me/avatar called; image hidden; placeholder visible; badge = "No avatar"
    await expect(page.locator('#profile-avatar-img')).toHaveClass(/d-none/)
    await expect(page.locator('#avatar-placeholder')).not.toHaveClass(/d-none/)
    await expect(page.locator('#avatar-source-badge')).toHaveText('No avatar')
  })

  test.skip('P-26: Cancel delete confirm dialog does nothing', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    const avatarSrc = await page.locator('#avatar-preview').getAttribute('src')
    page.on('dialog', dialog => dialog.dismiss())
    await page.locator('#avatar-delete-btn').click()
    // No DELETE /users/me/avatar call; avatar state unchanged
    await expect(page.locator('#avatar-preview')).toHaveAttribute('src', avatarSrc!)
  })

})

// =============================================================================
// Gravatar Toggle
// =============================================================================
test.describe('Gravatar Toggle', () => {

  test.skip('P-27: Enable gravatar toggle calls API and shows avatar', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#gravatar-toggle').check()
    // PUT /users/me/avatar-source with {source:"gravatar"}; toast "Gravatar enabled."
    await expect(page.locator('#profile-avatar-img')).toBeVisible()
    await expect(page.locator('#avatar-source-badge')).toHaveText('Gravatar')
  })

  test.skip('P-28: Disable gravatar toggle restores placeholder', async ({ page }) => {
    // TODO: requires auth session fixture + user with gravatar enabled
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#gravatar-toggle').uncheck()
    // PUT /users/me/avatar-source with {source:"none"}; toast "Gravatar disabled."
    await expect(page.locator('#avatar-placeholder')).toBeVisible()
    await expect(page.locator('#avatar-source-badge')).toHaveText('No avatar')
  })

  test.skip('P-29: Gravatar API failure reverts toggle state', async ({ page }) => {
    // TODO: requires auth session fixture + API mock for failure
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    const initialChecked = await page.locator('#gravatar-toggle').isChecked()
    await page.locator('#gravatar-toggle').click()
    // API fails; toast shows error; toggle reverts to original state
    await expect(page.locator('#gravatar-toggle')).toBeChecked({ checked: initialChecked })
  })

})

// =============================================================================
// Preferences — #preferences-form
// =============================================================================
test.describe('Preferences — #preferences-form', () => {

  test.skip('P-30: Save theme, language, and timezone preferences', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#pref-theme').selectOption('dark')
    await page.locator('#pref-locale').selectOption('zh-TW')
    await page.locator('#pref-timezone').selectOption('Asia/Taipei')
    await page.locator('#preferences-form button[type="submit"]').click()
    // PUT /users/me/preferences with {theme:"dark",locale:"zh-TW",timezone:"Asia/Taipei",...}; toast "Preferences saved."
    await expect(page.locator('.toast-body, .toast')).toContainText('Preferences saved.')
  })

  test.skip('P-31: Preferences pre-filled from profile data', async ({ page }) => {
    // TODO: requires auth session fixture + user with existing preferences
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    // Select values should match profile.preferences values
    await expect(page.locator('#pref-theme')).toHaveValue('dark')
    await expect(page.locator('#pref-locale')).toHaveValue('zh-TW')
    await expect(page.locator('#pref-timezone')).toHaveValue('Asia/Taipei')
  })

})

// =============================================================================
// Sidebar Navigation
// =============================================================================
test.describe('Sidebar Navigation', () => {

  test.skip('P-32: Profile sidebar link is active', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await expect(page.locator('.nav-item.active a[href*="/users/profile"]')).toBeVisible()
  })

  test.skip('P-33: Security link navigates to /users/security', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('a[href*="/users/security"]').click()
    await expect(page).toHaveURL(/\/users\/security/)
  })

})

// =============================================================================
// Edit User Page — /users/edit?id={userId}
// =============================================================================
test.describe('Edit User Page — /users/edit', () => {

  test.skip('P-34: Page loads user data from API and populates form', async ({ page }) => {
    // TODO: requires auth session fixture (admin)
    await page.goto('/users/edit?id=2', { waitUntil: 'networkidle' })
    await expect(page.locator('#edit-user-email')).not.toHaveValue('')
    await expect(page.locator('#edit-user-username')).not.toHaveValue('')
    await expect(page.locator('#edit-user-full-name')).toBeVisible()
    await expect(page.locator('#edit-user-status')).toBeVisible()
    // Role checkboxes checked according to user roles
    await expect(page.locator('#role-admin')).toBeChecked()
    await expect(page.locator('#role-user')).toBeChecked()
  })

  test.skip('P-35: Save user info successfully', async ({ page }) => {
    // TODO: requires auth session fixture (admin)
    await page.goto('/users/edit?id=2', { waitUntil: 'networkidle' })
    await page.locator('#edit-user-email').fill('updated@example.com')
    await page.locator('#edit-username').fill('newuser')
    await page.locator('#edit-user-form button[type="submit"]').click()
    // PUT /admin/users/{id} called; toast "User updated successfully."
    await expect(page.locator('.toast-body, .toast')).toContainText('User updated successfully.')
  })

  test.skip('P-36: Invalid email format shows field error', async ({ page }) => {
    // TODO: requires auth session fixture (admin)
    await page.goto('/users/edit?id=2', { waitUntil: 'networkidle' })
    await page.locator('#edit-user-email').fill('invalidemail')
    await page.locator('#edit-user-form button[type="submit"]').click()
    await expect(page.locator('#edit-user-email')).toHaveClass(/is-invalid/)
    await expect(page.locator('#edit-user-form .invalid-feedback')).toBeVisible()
  })

  test.skip('P-37: Invalid username format shows field error', async ({ page }) => {
    // TODO: requires auth session fixture (admin)
    await page.goto('/users/edit?id=2', { waitUntil: 'networkidle' })
    await page.locator('#edit-user-username').fill('InvalidUser')
    await page.locator('#edit-user-form button[type="submit"]').click()
    await expect(page.locator('#edit-user-username')).toHaveClass(/is-invalid/)
  })

  test.skip('P-38: Block user sets status to blocked', async ({ page }) => {
    // TODO: requires auth session fixture (admin)
    await page.goto('/users/edit?id=2', { waitUntil: 'networkidle' })
    await page.locator('#edit-user-status').selectOption('blocked')
    await page.locator('#edit-user-form button[type="submit"]').click()
    // PUT /admin/users/{id} with {status:"blocked"}; toast appears
    await expect(page.locator('.toast-body, .toast')).toBeVisible()
  })

  test.skip('P-39: No id parameter shows error message', async ({ page }) => {
    // TODO: requires auth session fixture (admin)
    await page.goto('/users/edit', { waitUntil: 'networkidle' })
    await expect(page.locator('#edit-user-form')).toContainText('No user ID specified in URL.')
  })

  test.skip('P-40: Non-existent user ID shows API error', async ({ page }) => {
    // TODO: requires auth session fixture (admin)
    await page.goto('/users/edit?id=99999', { waitUntil: 'networkidle' })
    // API returns 404; form shows error message
    await expect(page.locator('#edit-user-form')).toContainText(/error/i)
  })

  test.skip('P-41: Non-admin user access denied', async ({ page }) => {
    // TODO: requires auth session fixture (role=user, not admin)
    await page.goto('/users/edit?id=2', { waitUntil: 'networkidle' })
    await expect(page.locator('#edit-user-form')).toContainText('Access denied. Administrator privileges required.')
  })

  test.skip('P-42: Cancel button navigates to /settings/users', async ({ page }) => {
    // TODO: requires auth session fixture (admin)
    await page.goto('/users/edit?id=2', { waitUntil: 'networkidle' })
    await page.locator('.card-footer a[href*="/settings/users"]').click()
    await expect(page).toHaveURL(/\/settings\/users/)
  })

  test.skip('P-43: Back button navigates to /settings/users', async ({ page }) => {
    // TODO: requires auth session fixture (admin)
    await page.goto('/users/edit?id=2', { waitUntil: 'networkidle' })
    await page.locator('.page-header a[href*="/settings/users"]').click()
    await expect(page).toHaveURL(/\/settings\/users/)
  })

})
