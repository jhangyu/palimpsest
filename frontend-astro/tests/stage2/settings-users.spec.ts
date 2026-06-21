/**
 * S2-07: Settings User Management — Playwright Tests
 * Spec: docs/test-specs/s2-07-settings-users.md
 *
 * Covers: /settings/users page — Page load, Add User form validation,
 * User list & search, Block/Unblock, Delete user, Edit navigation,
 * Pagination, Status/Role badges, API error handling.
 *
 * Tests requiring authentication are marked test.skip until session fixture lands.
 * Run: npx playwright test tests/stage2/settings-users.spec.ts
 */
import { test, expect } from '@playwright/test'

// =============================================================================
// Page Load
// =============================================================================
test.describe('Page Load', () => {

  test.skip('7.01 Page loads: spinner then user table [T01]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')
    await expect(page.locator('#user-list-container .spinner-border')).toBeVisible()
    await expect(page.locator('#user-list-container .table')).toBeVisible()
    const rows = page.locator('.table tbody tr')
    await expect(rows).not.toHaveCount(0)
    const headers = page.locator('.table thead th')
    await expect(headers).toHaveCount(5)
    await expect(headers.nth(0)).toContainText('User')
    await expect(headers.nth(1)).toContainText('Roles')
    await expect(headers.nth(2)).toContainText('Status')
    await expect(headers.nth(3)).toContainText('Last Login')
    await expect(headers.nth(4)).toContainText('Actions')
  })

  test.skip('7.02 Non-admin user: user-list-container shows Access Denied [T02]', async ({ page }) => {
    // TODO: requires auth session fixture (non-admin account)
    await page.goto('/settings/users')
    const alert = page.locator('#user-list-container .alert-danger')
    await expect(alert).toBeVisible()
    await expect(alert).toContainText('Access denied. Administrator privileges required.')
  })

  test.skip('7.03 Non-admin user: add-user-form shows Access Denied [T03]', async ({ page }) => {
    // TODO: requires auth session fixture (non-admin account)
    await page.goto('/settings/users')
    const alert = page.locator('#add-user-form .alert-danger')
    await expect(alert).toBeVisible()
    await expect(alert).toContainText('Access denied.')
  })
})

// =============================================================================
// Add User — Form Validation
// =============================================================================
test.describe('Add User — Form Validation', () => {

  test.skip('7.04 Email empty submit shows validation error [T04]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')
    await page.locator('#add-user-email').clear()
    await page.locator('#add-user-form button[type="submit"]').click()
    await expect(page.locator('#add-user-email.is-invalid')).toBeVisible()
    await expect(page.locator('#add-user-email ~ .invalid-feedback')).toContainText('Valid email is required.')
  })

  test.skip('7.05 Email invalid format shows validation error [T05]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')
    await page.locator('#add-user-email').fill('notanemail')
    await page.locator('#add-user-form button[type="submit"]').click()
    await expect(page.locator('#add-user-email.is-invalid')).toBeVisible()
  })

  test.skip('7.06 Username invalid format (uppercase/digits) shows validation error [T06]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')
    await page.locator('#add-user-username').fill('User123')
    await page.locator('#add-user-form button[type="submit"]').click()
    await expect(page.locator('#add-user-username.is-invalid')).toBeVisible()
    await expect(page.locator('#add-user-username ~ .invalid-feedback')).toContainText('Username must be 1-20 lowercase English letters only.')
  })

  test.skip('7.07 Username empty submit shows validation error [T07]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')
    await page.locator('#add-user-email').fill('valid@example.com')
    await page.locator('#add-user-username').clear()
    await page.locator('#add-user-form button[type="submit"]').click()
    await expect(page.locator('#add-user-username.is-invalid')).toBeVisible()
  })

  test.skip('7.08 Successfully create user with user role only [T08]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    // Intercept POST /admin/users
    const postPromise = page.waitForRequest(req =>
      req.method() === 'POST' && req.url().includes('/admin/users')
    )

    await page.locator('#add-user-email').fill('newuser@example.com')
    await page.locator('#add-user-username').fill('newuser')
    // #role-user should be checked by default
    await expect(page.locator('#role-user')).toBeChecked()
    await page.locator('#add-user-form button[type="submit"]').click()

    const postReq = await postPromise
    const body = postReq.postDataJSON()
    expect(body.email).toBe('newuser@example.com')
    expect(body.username).toBe('newuser')
    expect(body.roles).toEqual(['user'])

    // Success banner becomes visible
    await expect(page.locator('#add-user-success')).toBeVisible()

    // Form resets
    await expect(page.locator('#add-user-email')).toHaveValue('')
    await expect(page.locator('#add-user-username')).toHaveValue('')
  })

  test.skip('7.09 Successfully create user with admin + user roles [T09]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    const postPromise = page.waitForRequest(req =>
      req.method() === 'POST' && req.url().includes('/admin/users')
    )

    await page.locator('#add-user-email').fill('adminuser@example.com')
    await page.locator('#add-user-username').fill('adminuser')
    await page.locator('#role-admin').check()
    await page.locator('#add-user-form button[type="submit"]').click()

    const postReq = await postPromise
    const body = postReq.postDataJSON()
    expect(body.roles).toContain('admin')
    expect(body.roles).toContain('user')

    await expect(page.locator('#add-user-success')).toBeVisible()
  })

  test.skip('7.10 Duplicate email shows server error on email field [T10]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    // Mock POST /admin/users to return email conflict error
    await page.route('**/admin/users', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'email already exists' }),
        })
      } else {
        await route.continue()
      }
    })

    await page.locator('#add-user-email').fill('existing@example.com')
    await page.locator('#add-user-username').fill('newuser')
    await page.locator('#add-user-form button[type="submit"]').click()

    await expect(page.locator('#add-user-email.is-invalid')).toBeVisible()
  })

  test.skip('7.11 Duplicate username shows server error on username field [T11]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    await page.route('**/admin/users', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'username already exists' }),
        })
      } else {
        await route.continue()
      }
    })

    await page.locator('#add-user-email').fill('unique@example.com')
    await page.locator('#add-user-username').fill('existinguser')
    await page.locator('#add-user-form button[type="submit"]').click()

    await expect(page.locator('#add-user-username.is-invalid')).toBeVisible()
  })

  test.skip('7.12 Submit button shows loading state (disabled + spinner) [T12]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    // Intercept POST and delay response
    await page.route('**/admin/users', async (route) => {
      if (route.request().method() === 'POST') {
        await new Promise(resolve => setTimeout(resolve, 2000))
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 1, email: 'test@example.com', username: 'test' }),
        })
      } else {
        await route.continue()
      }
    })

    await page.locator('#add-user-email').fill('test@example.com')
    await page.locator('#add-user-username').fill('testuser')
    await page.locator('#add-user-form button[type="submit"]').click()

    // Button should be disabled with spinner text during request
    const submitBtn = page.locator('#add-user-form button[type="submit"]')
    await expect(submitBtn).toBeDisabled()
    await expect(submitBtn).toContainText('Saving...')

    // After request completes, button re-enables
    await expect(submitBtn).toBeEnabled()
  })
})

// =============================================================================
// User List & Search
// =============================================================================
test.describe('User List & Search', () => {

  test.skip('7.13 Search input triggers live filtering [T13]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')
    await expect(page.locator('.table tbody tr')).not.toHaveCount(0)

    const searchPromise = page.waitForRequest(req =>
      req.url().includes('/admin/users') && req.url().includes('search=')
    )

    await page.locator('#user-search-input').fill('admin')
    await searchPromise

    // List updates with matching users, page resets to 1
    await expect(page.locator('.table tbody tr')).not.toHaveCount(0)
  })

  test.skip('7.14 Search with no results shows "No users found." [T14]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    await page.route('**/admin/users?*', async (route) => {
      if (route.request().url().includes('search=')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ users: [], total: 0, page: 1, page_size: 20 }),
        })
      } else {
        await route.continue()
      }
    })

    await page.locator('#user-search-input').fill('zzzznonexistent')
    await expect(page.locator('#user-list-container p.text-muted')).toContainText('No users found.')
  })

  test.skip('7.15 Clear search restores full user list [T15]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')
    const initialCount = await page.locator('.table tbody tr').count()

    await page.locator('#user-search-input').fill('somequery')
    await page.locator('#user-search-input').clear()

    await expect(page.locator('.table tbody tr')).toHaveCount(initialCount)
  })

  test.skip('7.16 Each row displays correct columns: username, email, roles, status, last login, actions [T16]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')
    await expect(page.locator('.table tbody tr').first()).toBeVisible()

    const firstRow = page.locator('.table tbody tr').first()
    // td[0]: username + email
    const userCell = firstRow.locator('td').nth(0)
    await expect(userCell).not.toBeEmpty()

    // td[1]: role badges
    const rolesCell = firstRow.locator('td').nth(1)
    await expect(rolesCell).toBeVisible()

    // td[2]: status badge
    const statusCell = firstRow.locator('td').nth(2)
    await expect(statusCell).toBeVisible()

    // td[3]: last login
    const lastLoginCell = firstRow.locator('td').nth(3)
    await expect(lastLoginCell).toBeVisible()

    // td[4]: action buttons
    const actionsCell = firstRow.locator('td').nth(4)
    await expect(actionsCell).toBeVisible()
  })
})

// =============================================================================
// Block / Unblock
// =============================================================================
test.describe('Block / Unblock', () => {

  test.skip('7.17 Block active user: PUT with status blocked, toast, badge update [T17]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    const putPromise = page.waitForRequest(req =>
      req.method() === 'PUT' && req.url().match(/\/admin\/users\/\d+$/) !== null
    )

    const blockBtn = page.locator('button[data-action="toggle-block"][data-status="active"]').first()
    await blockBtn.click()

    const putReq = await putPromise
    const body = putReq.postDataJSON()
    expect(body.status).toBe('blocked')

    // Toast shows "User blocked."
    await expect(page.locator('.toast-body, .toast')).toContainText('User blocked.')

    // Badge updates to Blocked
    await expect(page.locator('.badge.bg-danger-subtle')).toBeVisible()
  })

  test.skip('7.18 Unblock blocked user: PUT with status active, toast, badge update [T18]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    const putPromise = page.waitForRequest(req =>
      req.method() === 'PUT' && req.url().match(/\/admin\/users\/\d+$/) !== null
    )

    const unblockBtn = page.locator('button[data-action="toggle-block"][data-status="blocked"]').first()
    await unblockBtn.click()

    const putReq = await putPromise
    const body = putReq.postDataJSON()
    expect(body.status).toBe('active')

    await expect(page.locator('.toast-body, .toast')).toContainText('User unblocked.')
    await expect(page.locator('.badge.bg-success-subtle')).toBeVisible()
  })

  test.skip('7.19 Block/Unblock button disabled during request [T19]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    // Intercept PUT and delay response
    await page.route('**/admin/users/*', async (route) => {
      if (route.request().method() === 'PUT') {
        await new Promise(resolve => setTimeout(resolve, 2000))
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 1, status: 'blocked' }),
        })
      } else {
        await route.continue()
      }
    })

    const toggleBtn = page.locator('button[data-action="toggle-block"]').first()
    await toggleBtn.click()

    await expect(page.locator('button[data-action="toggle-block"]:disabled')).toBeVisible()
  })

  test.skip('7.20 Block/Unblock API failure shows danger toast [T20]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    await page.route('**/admin/users/*', async (route) => {
      if (route.request().method() === 'PUT') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Internal server error' }),
        })
      } else {
        await route.continue()
      }
    })

    const toggleBtn = page.locator('button[data-action="toggle-block"]').first()
    await toggleBtn.click()

    // Toast shows danger variant
    await expect(page.locator('.toast.bg-danger, .toast-body')).toBeVisible()

    // Button re-enabled
    await expect(toggleBtn).toBeEnabled()
  })
})

// =============================================================================
// Delete User
// =============================================================================
test.describe('Delete User', () => {

  test.skip('7.21 Delete button triggers confirm dialog with username [T21]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    let confirmMessage = ''
    await page.on('dialog', async (dialog) => {
      confirmMessage = dialog.message()
      await dialog.dismiss()
    })

    const deleteBtn = page.locator('button[data-action="delete-user"]').first()
    const username = await deleteBtn.getAttribute('data-username') || ''
    await deleteBtn.click()

    expect(confirmMessage).toContain('Delete user')
    expect(confirmMessage).toContain(username)
    expect(confirmMessage).toContain('This cannot be undone.')
  })

  test.skip('7.22 Cancel confirm does not delete user, list unchanged [T22]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    let deleteRequested = false
    await page.on('dialog', async (dialog) => {
      await dialog.dismiss()
    })
    page.on('request', req => {
      if (req.method() === 'DELETE' && req.url().includes('/admin/users/')) {
        deleteRequested = true
      }
    })

    const rowCount = await page.locator('.table tbody tr').count()
    const deleteBtn = page.locator('button[data-action="delete-user"]').first()
    await deleteBtn.click()

    expect(deleteRequested).toBe(false)
    await expect(page.locator('.table tbody tr')).toHaveCount(rowCount)
  })

  test.skip('7.23 Confirm delete: DELETE API call, toast, list reloads [T23]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    await page.on('dialog', async (dialog) => {
      await dialog.accept()
    })

    const deletePromise = page.waitForRequest(req =>
      req.method() === 'DELETE' && req.url().match(/\/admin\/users\/\d+$/) !== null
    )

    const deleteBtn = page.locator('button[data-action="delete-user"]').first()
    await deleteBtn.click()

    await deletePromise

    // Toast shows "User deleted."
    await expect(page.locator('.toast-body, .toast')).toContainText('User deleted.')
  })

  test.skip('7.24 Delete button disabled during request [T24]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    await page.on('dialog', async (dialog) => {
      await dialog.accept()
    })

    await page.route('**/admin/users/*', async (route) => {
      if (route.request().method() === 'DELETE') {
        await new Promise(resolve => setTimeout(resolve, 2000))
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'ok' }),
        })
      } else {
        await route.continue()
      }
    })

    const deleteBtn = page.locator('button[data-action="delete-user"]').first()
    await deleteBtn.click()

    await expect(page.locator('button[data-action="delete-user"]:disabled')).toBeVisible()
  })

  test.skip('7.25 Delete API failure shows danger toast, button re-enabled [T25]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    await page.on('dialog', async (dialog) => {
      await dialog.accept()
    })

    await page.route('**/admin/users/*', async (route) => {
      if (route.request().method() === 'DELETE') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Internal server error' }),
        })
      } else {
        await route.continue()
      }
    })

    const deleteBtn = page.locator('button[data-action="delete-user"]').first()
    await deleteBtn.click()

    // Toast shows danger
    await expect(page.locator('.toast.bg-danger, .toast-body')).toBeVisible()

    // Button re-enabled
    await expect(deleteBtn).toBeEnabled()
  })
})

// =============================================================================
// Edit Button Navigation
// =============================================================================
test.describe('Edit Button Navigation', () => {

  test.skip('7.26 Click Edit navigates to /users/edit?id={userId} [T26]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    const editLink = page.locator('a.btn-outline-secondary[href*="/users/edit?id="]').first()
    const href = await editLink.getAttribute('href')
    await editLink.click()

    // URL should contain /users/edit?id=
    await expect(page).toHaveURL(/\/users\/edit\?id=/)
    // Verify the id in URL matches the href
    expect(page.url()).toContain(href || '/users/edit?id=')
  })
})

// =============================================================================
// Pagination
// =============================================================================
test.describe('Pagination', () => {

  test.skip('7.27 No pagination when users ≤ 20 [T27]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    // Mock API to return ≤ 20 users
    await page.route('**/admin/users*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          users: Array.from({ length: 5 }, (_, i) => ({
            id: i + 1, email: `user${i}@test.com`, username: `user${i}`,
            roles: ['user'], status: 'active', last_login: null,
          })),
          total: 5, page: 1, page_size: 20,
        }),
      })
    })

    await page.goto('/settings/users')
    await expect(page.locator('.pagination')).toHaveCount(0)
  })

  test.skip('7.28 Pagination visible when users > 20, current page active [T28]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    // Mock API to return > 20 users
    await page.route('**/admin/users*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          users: Array.from({ length: 20 }, (_, i) => ({
            id: i + 1, email: `user${i}@test.com`, username: `user${i}`,
            roles: ['user'], status: 'active', last_login: null,
          })),
          total: 45, page: 1, page_size: 20,
        }),
      })
    })

    await page.goto('/settings/users')
    await expect(page.locator('nav ul.pagination')).toBeVisible()
    await expect(page.locator('li.page-item.active')).toBeVisible()
  })

  test.skip('7.29 Click page 2 triggers GET with page=2, list updates [T29]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    // Mock initial load with pagination
    await page.route('**/admin/users*', async (route) => {
      const url = new URL(route.request().url())
      const currentPage = url.searchParams.get('page') || '1'
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          users: Array.from({ length: 20 }, (_, i) => ({
            id: (Number(currentPage) - 1) * 20 + i + 1,
            email: `user${(Number(currentPage) - 1) * 20 + i}@test.com`,
            username: `user${(Number(currentPage) - 1) * 20 + i}`,
            roles: ['user'], status: 'active', last_login: null,
          })),
          total: 45, page: Number(currentPage), page_size: 20,
        }),
      })
    })

    await page.goto('/settings/users')

    const page2Promise = page.waitForRequest(req =>
      req.url().includes('/admin/users') && req.url().includes('page=2')
    )

    await page.locator('button.page-link[data-page="2"]').click()
    await page2Promise

    // List updates with page 2 content
    await expect(page.locator('.table tbody tr')).not.toHaveCount(0)
  })
})

// =============================================================================
// Status / Role Badges
// =============================================================================
test.describe('Status / Role Badges', () => {

  test.skip('7.30 Active user shows green Active badge [T30]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    const activeBadge = page.locator('.badge.bg-success-subtle.text-success')
    await expect(activeBadge.first()).toBeVisible()
    await expect(activeBadge.first()).toHaveText('Active')
  })

  test.skip('7.31 Blocked user shows red Blocked badge [T31]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    const blockedBadge = page.locator('.badge.bg-danger-subtle.text-danger')
    await expect(blockedBadge.first()).toBeVisible()
    await expect(blockedBadge.first()).toHaveText('Blocked')
  })

  test.skip('7.32 User with no roles shows "—" placeholder [T32]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    // Find a user row with "—" in roles column
    const placeholder = page.locator('td:nth-child(2) .text-muted')
    await expect(placeholder.first()).toHaveText('—')
  })
})

// =============================================================================
// API Error Handling
// =============================================================================
test.describe('API Error Handling', () => {

  test.skip('7.33 401 Unauthorized redirects to login page [T33]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/users')

    // Mock any API call to return 401
    await page.route('**/admin/users*', async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Unauthorized' }),
      })
    })

    await page.goto('/settings/users')

    // Should redirect to login page
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })

  test.skip('7.34 User list load failure shows alert-danger with error message [T34]', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.route('**/admin/users*', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      })
    })

    await page.goto('/settings/users')

    const alert = page.locator('#user-list-container .alert-danger')
    await expect(alert).toBeVisible()
    await expect(alert).toContainText(/error/i)
  })
})
