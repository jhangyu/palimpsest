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

  test('P-01: Page loads profile from API and populates form fields', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await expect(page.locator('#profile-full-name')).not.toHaveValue('')
    await expect(page.locator('#profile-email')).not.toHaveValue('')
    await expect(page.locator('#profile-username')).not.toHaveValue('')
    await expect(page.locator('[data-session="user-name"]').first()).not.toHaveText('Loading...')
  })

  test('P-02: Pending email banner visible when pending_email exists', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: 'new@test.com', avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await expect(page.locator('#pending-email-banner')).toBeVisible()
    await expect(page.locator('#pending-email-text')).toBeVisible()
    await expect(page.locator('#pending-email-text')).not.toHaveText('')
  })

  test('P-03: Pending email banner hidden when no pending_email', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await expect(page.locator('#pending-email-banner')).not.toBeVisible()
  })

  test('P-04: Avatar image visible when avatar_source is upload or gravatar', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'upload', avatar_url: '/avatars/test.jpg',
            status: 'active', roles: ['admin'], email_verified_at: null,
            preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await expect(page.locator('#profile-avatar-img')).not.toHaveClass(/d-none/)
    await expect(page.locator('#avatar-placeholder')).toHaveClass(/d-none/)
  })

  test('P-05: Placeholder icon visible when avatar_source is none', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await expect(page.locator('#avatar-placeholder')).toBeVisible()
    await expect(page.locator('#profile-avatar-img')).toHaveClass(/d-none/)
  })

  test('P-06: Avatar source badge shows correct text', async ({ page }) => {
    // source=none → "No avatar"; source=upload → "Uploaded photo"; source=gravatar → "Gravatar"
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await expect(page.locator('#avatar-source-badge')).toContainText(/No avatar|Uploaded photo|Gravatar/)
  })

  test('P-07: Gravatar toggle unchecked by default for new user', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await expect(page.locator('#gravatar-toggle')).not.toBeChecked()
  })

})

// =============================================================================
// Display Name — #full-name-form
// =============================================================================
test.describe('Display Name — #full-name-form', () => {
  test.describe.configure({ mode: 'serial' })

  test('P-08: Save full name successfully', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else if (route.request().method() === 'PUT') {
        // Delay to ensure button stays disabled long enough for assertion
        await new Promise(r => setTimeout(r, 400))
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ full_name: 'New Display Name' })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-full-name').fill('New Display Name')
    await page.locator('#full-name-form button[type="submit"]').click()
    // Button should enter loading state; PUT /users/me called; toast "Full name updated." appears
    await expect(page.locator('#full-name-form button[type="submit"]')).toBeDisabled()
    await expect(page.locator('.alert.position-fixed')).toContainText('Full name updated.')
  })

  test('P-09: Save empty full name allowed', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-full-name').fill('')
    await page.locator('#full-name-form button[type="submit"]').click()
    // PUT /users/me with {full_name: ""} should succeed; toast appears
    await expect(page.locator('.alert.position-fixed')).toBeVisible()
  })

})

// =============================================================================
// Email Address — #email-change-form
// =============================================================================
test.describe('Email Address — #email-change-form', () => {
  test.describe.configure({ mode: 'serial' })

  test('P-10: Submit email change shows pending verification banner', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.route('**/users/me/email', async (route) => {
      if (route.request().method() === 'PUT') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-email').fill('newemail@example.com')
    await page.locator('#profile-email-password').fill('currentpassword')
    await page.locator('#email-change-form button[type="submit"]').click()
    // PUT /users/me/email called; toast "Verification email sent..."; banner visible; password cleared
    await expect(page.locator('#pending-email-banner')).toBeVisible()
    await expect(page.locator('#profile-email-password')).toHaveValue('')
  })

  test('P-11: Invalid email format shows field error', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    // Wait for profile form to be populated (indicates initProfilePage completed and bindProfileForms ran)
    await page.waitForFunction(() => {
      const el = document.getElementById('profile-email') as HTMLInputElement | null
      return el && el.value !== ''
    }, { timeout: 5000 })
    await page.locator('#profile-email').fill('invalidemail')
    await page.locator('#email-change-form button[type="submit"]').click()
    await expect(page.locator('#profile-email')).toHaveClass(/is-invalid/)
    await expect(page.locator('#email-change-form .invalid-feedback')).toBeVisible()
  })

  test('P-12: Missing password shows field error', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-email').fill('valid@example.com')
    // Leave password empty
    await page.locator('#email-change-form button[type="submit"]').click()
    await expect(page.locator('#profile-email-password')).toHaveClass(/is-invalid/)
  })

  test('P-13: Same email as current shows field error', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    // Wait for profile form to be populated before reading current email value
    await page.waitForFunction(() => {
      const el = document.getElementById('profile-email') as HTMLInputElement | null
      return el && el.value !== ''
    }, { timeout: 5000 })
    const currentEmail = await page.locator('#profile-email').inputValue()
    await page.locator('#profile-email').fill(currentEmail)
    await page.locator('#email-change-form button[type="submit"]').click()
    await expect(page.locator('#profile-email')).toHaveClass(/is-invalid/)
    // Hint: "same as current"
    await expect(page.locator('#email-change-form .invalid-feedback')).toContainText(/same as current/i)
  })

  test('P-14: Wrong password API error shown on field', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.route('**/users/me/email', async (route) => {
      if (route.request().method() === 'PUT') {
        await route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Incorrect password' })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-email').fill('newemail@example.com')
    await page.locator('#profile-email-password').fill('wrongpassword')
    await page.locator('#email-change-form button[type="submit"]').click()
    // Error message displayed in field or toast
    await expect(page.locator('#email-change-form .invalid-feedback')).toBeVisible()
  })

  test('P-15: Pending banner disappears after email verification', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'newemail@example.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
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
  test.describe.configure({ mode: 'serial' })

  test('P-16: Save valid lowercase username successfully', async ({ page }) => {
    await page.route('**/users/me/username', async (route) => {
      if (route.request().method() === 'PUT') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-username').fill('validname')
    await page.locator('#username-change-form button[type="submit"]').click()
    // PUT /users/me/username called; toast "Username updated successfully."
    await expect(page.locator('.alert.position-fixed')).toContainText('Username updated successfully.')
  })

  test('P-17: Username with uppercase characters shows field error', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    // Wait for profile form to be populated (indicates initProfilePage completed and bindProfileForms ran)
    await page.waitForFunction(() => {
      const el = document.getElementById('profile-username') as HTMLInputElement | null
      return el && el.value !== ''
    }, { timeout: 5000 })
    await page.locator('#profile-username').fill('Admin')
    await page.locator('#username-change-form button[type="submit"]').click()
    await expect(page.locator('#profile-username')).toHaveClass(/is-invalid/)
    await expect(page.locator('#username-change-form .invalid-feedback')).toBeVisible()
  })

  test('P-18: Username with digits or special chars shows field error', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-username').fill('user123')
    await page.locator('#username-change-form button[type="submit"]').click()
    await expect(page.locator('#profile-username')).toHaveClass(/is-invalid/)
    await expect(page.locator('#username-change-form .invalid-feedback')).toBeVisible()
  })

  test('P-19: Reserved username shows API error', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.route('**/users/me/username', async (route) => {
      if (route.request().method() === 'PUT') {
        await route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'This is a reserved username' })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#profile-username').fill('admin')
    await page.locator('#username-change-form button[type="submit"]').click()
    // API returns 4xx; field shows "reserved username" error
    await expect(page.locator('#profile-username')).toHaveClass(/is-invalid/)
    await expect(page.locator('#username-change-form .invalid-feedback')).toContainText(/reserved/i)
  })

  test('P-20: Duplicate username shows conflict error', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.route('**/users/me/username', async (route) => {
      if (route.request().method() === 'PUT') {
        await route.fulfill({
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Username already taken' })
        })
      } else {
        await route.continue()
      }
    })
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
  test.describe.configure({ mode: 'serial' })

  test('P-21: Upload button triggers file input', async ({ page }) => {
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    const fileInput = page.locator('#avatar-file-input')
    await expect(fileInput).toHaveAttribute('accept', 'image/jpeg,image/png,image/webp')
    // Clicking #avatar-upload-btn should trigger #avatar-file-input click
    await page.locator('#avatar-upload-btn').click()
  })

  test('P-22: Upload valid JPEG shows avatar image and hides placeholder', async ({ page }) => {
    await page.route('**/users/me/avatar', async (route) => {
      if (route.request().method() === 'PUT') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ avatar_url: '/avatars/uploaded.jpg' })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    // Upload 1KB JPEG via setInputFiles
    await page.locator('#avatar-file-input').setInputFiles({
      name: 'avatar.jpg',
      mimeType: 'image/jpeg',
      buffer: Buffer.alloc(1024)
    })
    // PUT /users/me/avatar called; avatar visible; placeholder hidden; badge = "Uploaded photo"
    await expect(page.locator('#profile-avatar-img')).not.toHaveClass(/d-none/)
    await expect(page.locator('#avatar-placeholder')).toHaveClass(/d-none/)
    await expect(page.locator('#avatar-source-badge')).toHaveText('Uploaded photo')
  })

  test('P-23: Upload SVG shows format error toast', async ({ page }) => {
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#avatar-file-input').setInputFiles({
      name: 'image.svg',
      mimeType: 'image/svg+xml',
      buffer: Buffer.from('<svg></svg>')
    })
    // toast "Only JPEG, PNG, or WebP images are allowed."; no API call; file input cleared
    await expect(page.locator('.alert.position-fixed')).toContainText('Only JPEG, PNG, or WebP images are allowed.')
    await expect(page.locator('#avatar-file-input')).toHaveValue('')
  })

  test('P-24: Upload oversized image shows size error toast', async ({ page }) => {
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    // Upload >512KB PNG
    await page.locator('#avatar-file-input').setInputFiles({
      name: 'large.png',
      mimeType: 'image/png',
      buffer: Buffer.alloc(600 * 1024)
    })
    // toast "Image must be 512 KB or smaller."; no API call; file input cleared
    await expect(page.locator('.alert.position-fixed')).toContainText('Image must be 512 KB or smaller.')
    await expect(page.locator('#avatar-file-input')).toHaveValue('')
  })

})

// =============================================================================
// Profile Photo — Avatar Delete
// =============================================================================
test.describe('Profile Photo — Avatar Delete', () => {
  test.describe.configure({ mode: 'serial' })

  test('P-25: Delete avatar restores placeholder and hides image', async ({ page }) => {
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    page.on('dialog', dialog => dialog.accept())
    await page.locator('#avatar-delete-btn').click()
    // DELETE /users/me/avatar called; image hidden; placeholder visible; badge = "No avatar"
    await expect(page.locator('#profile-avatar-img')).toHaveClass(/d-none/)
    await expect(page.locator('#avatar-placeholder')).not.toHaveClass(/d-none/)
    await expect(page.locator('#avatar-source-badge')).toHaveText('No avatar')
  })

  test('P-26: Cancel delete confirm dialog does nothing', async ({ page }) => {
    test.slow()
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'upload', avatar_url: '/avatars/test.jpg',
            status: 'active', roles: ['admin'], email_verified_at: null,
            preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    page.on('dialog', dialog => dialog.dismiss())
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    const avatarSrc = await page.locator('#profile-avatar-img').getAttribute('src')
    await page.locator('#avatar-delete-btn').click()
    // No DELETE /users/me/avatar call; avatar state unchanged
    await expect(page.locator('#profile-avatar-img')).toHaveAttribute('src', avatarSrc!)
  })

})

// =============================================================================
// Gravatar Toggle
// =============================================================================
test.describe('Gravatar Toggle', () => {
  test.describe.configure({ mode: 'serial' })

  test('P-27: Enable gravatar toggle calls API and shows avatar', async ({ page }) => {
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#gravatar-toggle').check()
    // PUT /users/me/avatar-source with {source:"gravatar"}; toast "Gravatar enabled."
    await expect(page.locator('#profile-avatar-img')).toBeVisible()
    await expect(page.locator('#avatar-source-badge')).toHaveText('Gravatar')
  })

  test('P-28: Disable gravatar toggle restores placeholder', async ({ page }) => {
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#gravatar-toggle').uncheck()
    // PUT /users/me/avatar-source with {source:"none"}; toast "Gravatar disabled."
    await expect(page.locator('#avatar-placeholder')).toBeVisible()
    await expect(page.locator('#avatar-source-badge')).toHaveText('No avatar')
  })

  test('P-29: Gravatar API failure reverts toggle state', async ({ page }) => {
    await page.route('**/users/me', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1, email: 'user@test.com', username: 'testuser', full_name: 'Test User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.route('**/users/me/avatar-source', async (route) => {
      if (route.request().method() === 'PUT') {
        await route.fulfill({ status: 500, body: 'Server Error' })
      } else {
        await route.continue()
      }
    })
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
  test.describe.configure({ mode: 'serial' })

  test('P-30: Save theme, language, and timezone preferences', async ({ page }) => {
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('#pref-theme').selectOption('dark')
    await page.locator('#pref-locale').selectOption('zh-TW')
    await page.locator('#pref-timezone').selectOption('Asia/Taipei')
    await page.locator('#preferences-form button[type="submit"]').click()
    // PUT /users/me/preferences with {theme:"dark",locale:"zh-TW",timezone:"Asia/Taipei",...}; toast "Preferences saved."
    await expect(page.locator('.alert.position-fixed')).toContainText('Preferences saved.')
  })

  test('P-31: Preferences pre-filled from profile data', async ({ page }) => {
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

  test('P-32: Profile sidebar link is active', async ({ page }) => {
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await expect(page.locator('.sidebar .nav-item.active a[href*="/users/profile"]')).toBeVisible()
  })

  test('P-33: Security link navigates to /users/security', async ({ page }) => {
    await page.goto('/users/profile', { waitUntil: 'networkidle' })
    await page.locator('.sidebar a[href*="/users/security"]').click()
    await expect(page).toHaveURL(/\/users\/security/)
  })

})

// =============================================================================
// Edit User Page — /users/edit?id={userId}
// =============================================================================
test.describe('Edit User Page — /users/edit', () => {
  test.describe.configure({ mode: 'serial' })

  test('P-34: Page loads user data from API and populates form', async ({ page }) => {
    await page.route('**/admin/users/2', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 2, email: 'otheruser@test.com', username: 'otheruser', full_name: 'Other User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin', 'user'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/edit?id=2', { waitUntil: 'networkidle' })
    await expect(page.locator('#edit-user-email')).not.toHaveValue('')
    await expect(page.locator('#edit-user-username')).not.toHaveValue('')
    await expect(page.locator('#edit-user-full-name')).toBeVisible()
    await expect(page.locator('#edit-user-status')).toBeVisible()
    // Role checkboxes checked according to user roles
    await expect(page.locator('#role-admin')).toBeChecked()
    await expect(page.locator('#role-user')).toBeChecked()
  })

  test('P-35: Save user info successfully', async ({ page }) => {
    await page.route('**/admin/users/2', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 2, email: 'otheruser@test.com', username: 'otheruser', full_name: 'Other User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin', 'user'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else if (route.request().method() === 'PUT') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 2, email: 'updated@example.com', username: 'newuser' })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/edit?id=2', { waitUntil: 'networkidle' })
    await page.locator('#edit-user-email').fill('updated@example.com')
    await page.locator('#edit-user-username').fill('newuser')
    await page.locator('#edit-user-form button[type="submit"]').click()
    // PUT /admin/users/{id} called; toast "User updated successfully."
    await expect(page.locator('.alert.position-fixed')).toContainText('User updated successfully.')
  })

  test('P-36: Invalid email format shows field error', async ({ page }) => {
    await page.route('**/admin/users/2', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 2, email: 'otheruser@test.com', username: 'otheruser', full_name: 'Other User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin', 'user'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/edit?id=2', { waitUntil: 'networkidle' })
    await page.locator('#edit-user-email').fill('invalidemail')
    await page.locator('#edit-user-form button[type="submit"]').click()
    await expect(page.locator('#edit-user-email')).toHaveClass(/is-invalid/)
    await expect(page.locator('#edit-user-form .invalid-feedback')).toBeVisible()
  })

  test('P-37: Invalid username format shows field error', async ({ page }) => {
    await page.route('**/admin/users/2', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 2, email: 'otheruser@test.com', username: 'otheruser', full_name: 'Other User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin', 'user'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/edit?id=2', { waitUntil: 'networkidle' })
    await page.locator('#edit-user-username').fill('InvalidUser')
    await page.locator('#edit-user-form button[type="submit"]').click()
    await expect(page.locator('#edit-user-username')).toHaveClass(/is-invalid/)
  })

  test('P-38: Block user sets status to blocked', async ({ page }) => {
    await page.route('**/admin/users/2', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 2, email: 'otheruser@test.com', username: 'otheruser', full_name: 'Other User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin', 'user'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else if (route.request().method() === 'PUT') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 2, status: 'blocked' })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/edit?id=2', { waitUntil: 'networkidle' })
    await page.locator('#edit-user-status').selectOption('blocked')
    await page.locator('#edit-user-form button[type="submit"]').click()
    // PUT /admin/users/{id} with {status:"blocked"}; toast appears
    await expect(page.locator('.alert.position-fixed')).toBeVisible()
  })

  test('P-39: No id parameter shows error message', async ({ page }) => {
    await page.goto('/users/edit', { waitUntil: 'networkidle' })
    await expect(page.locator('#edit-user-form')).toContainText('No user ID specified in URL.')
  })

  test('P-40: Non-existent user ID shows API error', async ({ page }) => {
    await page.goto('/users/edit?id=99999', { waitUntil: 'networkidle' })
    // API returns 404; form shows error message (e.g. "User not found" or similar)
    await expect(page.locator('#edit-user-form')).toContainText(/error|not found/i)
  })

  test('P-41: Non-admin user access denied', async ({ page }) => {
    // Mock GET /admin/users/2 to return 403 — the error handler renders the detail message
    await page.route('**/admin/users/2', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 403,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Access denied. Administrator privileges required.' })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/edit?id=2', { waitUntil: 'networkidle' })
    await expect(page.locator('#edit-user-form')).toContainText('Access denied. Administrator privileges required.')
  })

  test('P-42: Cancel button navigates to /settings/users', async ({ page }) => {
    await page.route('**/admin/users/2', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 2, email: 'otheruser@test.com', username: 'otheruser', full_name: 'Other User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin', 'user'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/edit?id=2', { waitUntil: 'networkidle' })
    await page.locator('.card-footer a[href*="/settings/users"]').click()
    await expect(page).toHaveURL(/\/settings\/users/)
  })

  test('P-43: Back button navigates to /settings/users', async ({ page }) => {
    await page.route('**/admin/users/2', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 2, email: 'otheruser@test.com', username: 'otheruser', full_name: 'Other User',
            pending_email: null, avatar_source: 'none', status: 'active', roles: ['admin', 'user'],
            email_verified_at: null, preferences: {}, created_at: '2024-01-01', updated_at: '2024-01-01', last_login_at: null
          })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/edit?id=2', { waitUntil: 'networkidle' })
    await page.locator('.page-header a[href*="/settings/users"]').click()
    await expect(page).toHaveURL(/\/settings\/users/)
  })

})
