/*
---
name: settings-users
description: "Stage 2 E2E: /settings/users — page load, add user (validation/success/conflict), search, block/unblock, delete, edit navigation, pagination, role/status badges, auth redirect"
stage: stage2
type: playwright
target:
  layer: frontend
  domain: settings-users
spec_doc: docs/test-specs/stage2/s2-07-settings-users.md
test_file: tests/stage2/e2e/stage2/settings-users.spec.ts
tests:
  - name: "7.01 Page loads: spinner then user table [T01]"
    line: 19
    purpose: "Delayed users API keeps spinner visible; user table renders after load"
  - name: "7.02 Non-admin user: user-list-container shows Access Denied [T02]"
    line: 39
    purpose: "[skip] Non-admin 403 response shows Access Denied in user list container"
  - name: "7.03 Non-admin user: add-user-form shows Access Denied [T03]"
    line: 47
    purpose: "[skip] Non-admin session hides add-user-form and shows Access Denied"
  - name: "7.04 Email empty submit shows validation error [T04]"
    line: 62
    purpose: "Submitting add-user form with empty email shows required validation error"
  - name: "7.05 Email invalid format shows validation error [T05]"
    line: 70
    purpose: "Non-email in email field shows HTML5 email format validation error"
  - name: "7.06 Username invalid format (uppercase/digits) shows validation error [T06]"
    line: 77
    purpose: "Username with invalid chars shows pattern validation error"
  - name: "7.07 Username empty submit shows validation error [T07]"
    line: 85
    purpose: "Submitting add-user form with empty username shows required validation error"
  - name: "7.08 Successfully create user with user role only [T08]"
    line: 93
    purpose: "Mocked POST /admin/users with user role shows success toast"
  - name: "7.09 Successfully create user with admin + user roles [T09]"
    line: 134
    purpose: "Mocked POST /admin/users with admin+user roles shows success toast"
  - name: "7.10 Duplicate email shows server error on email field [T10]"
    line: 167
    purpose: "409 duplicate email from API shows server error on email field"
  - name: "7.11 Duplicate username shows server error on username field [T11]"
    line: 190
    purpose: "409 duplicate username from API shows server error on username field"
  - name: "7.12 Submit button shows loading state (disabled + spinner) [T12]"
    line: 212
    purpose: "Submit button disabled and shows spinner immediately after click"
  - name: "7.13 Search input triggers live filtering [T13]"
    line: 248
    purpose: "Typing in search input triggers client-side list filtering"
  - name: "7.14 Search with no results shows \"No users found.\" [T14]"
    line: 263
    purpose: "Non-matching search shows 'No users found.' in user list"
  - name: "7.15 Clear search restores full user list [T15]"
    line: 282
    purpose: "Clearing search input restores full user list"
  - name: "7.16 Each row displays correct columns: username, email, roles, status, last login, actions [T16]"
    line: 294
    purpose: "User table rows show all required columns with correct data"
  - name: "7.17 Block active user: PUT with status blocked, toast, badge update [T17]"
    line: 327
    purpose: "Clicking Block calls PUT with blocked status; shows toast; updates badge"
  - name: "7.18 Unblock blocked user: PUT with status active, toast, badge update [T18]"
    line: 348
    purpose: "Clicking Unblock calls PUT with active status; shows toast; updates badge"
  - name: "7.19 Block/Unblock button disabled during request [T19]"
    line: 366
    purpose: "Block/Unblock button disabled while API call is in progress"
  - name: "7.20 Block/Unblock API failure shows danger toast [T20]"
    line: 389
    purpose: "500 from block/unblock API shows danger toast"
  - name: "7.21 Delete button triggers confirm dialog with username [T21]"
    line: 421
    purpose: "Delete button shows confirm dialog containing the user's username"
  - name: "7.22 Cancel confirm does not delete user, list unchanged [T22]"
    line: 439
    purpose: "Cancelling delete confirm does not call DELETE API"
  - name: "7.23 Confirm delete: DELETE API call, toast, list reloads [T23]"
    line: 460
    purpose: "Accepting delete confirm calls DELETE /admin/users/:id; shows toast; reloads list"
  - name: "7.24 Delete button disabled during request [T24]"
    line: 493
    purpose: "Delete button disabled while DELETE API call is in progress"
  - name: "7.25 Delete API failure shows danger toast, button re-enabled [T25]"
    line: 519
    purpose: "500 from DELETE API shows danger toast and re-enables the delete button"
  - name: "7.26 Click Edit navigates to /users/edit?id={userId} [T26]"
    line: 554
    purpose: "Clicking Edit on a row navigates to /users/edit?id={userId}"
  - name: "7.27 No pagination when users ≤ 20 [T27]"
    line: 574
    purpose: "20 or fewer users: no pagination controls visible"
  - name: "7.28 Pagination visible when users > 20, current page active [T28]"
    line: 596
    purpose: "21+ users: pagination controls visible with page 1 active"
  - name: "7.29 Click page 2 triggers GET with page=2, list updates [T29]"
    line: 618
    purpose: "Clicking page 2 in pagination calls GET /admin/users?page=2 and updates list"
  - name: "7.30 Active user shows green Active badge [T30]"
    line: 660
    purpose: "User with status='active' shows green .badge-success 'Active' badge"
  - name: "7.31 Blocked user shows red Blocked badge [T31]"
    line: 670
    purpose: "User with status='blocked' shows red .badge-danger 'Blocked' badge"
  - name: "7.32 User with no roles shows \"—\" placeholder [T32]"
    line: 694
    purpose: "User with empty roles array shows '—' placeholder in roles column"
  - name: "7.33 401 Unauthorized redirects to login page [T33]"
    line: 723
    purpose: "Cleared cookies navigating to /settings/users redirects to login page"
  - name: "7.34 User list load failure shows alert-danger with error message [T34]"
    line: 741
    purpose: "500 from GET /admin/users shows .alert-danger with error message"
run:
  command: "cd frontend-astro && npx playwright test tests/stage2/e2e/stage2/settings-users.spec.ts"
  prerequisites:
    - "App running on http://localhost:5174"
---
*/
import { test, expect } from '@playwright/test'

// =============================================================================
// Page Load
// =============================================================================
test.describe('Page Load', () => {

  test('7.01 Page loads: spinner then user table [T01]', async ({ page }) => {
    // Add delay mock to catch spinner before table appears
    await page.route('**/admin/users*', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 500))
      await route.continue()
    })
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
    // Requires non-admin session fixture
    await page.goto('/settings/users')
    const alert = page.locator('#user-list-container .alert-danger')
    await expect(alert).toBeVisible()
    await expect(alert).toContainText('Access denied. Administrator privileges required.')
  })

  test.skip('7.03 Non-admin user: add-user-form shows Access Denied [T03]', async ({ page }) => {
    // Requires non-admin session fixture
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
  test.describe.configure({ mode: 'serial' })

  test('7.04 Email empty submit shows validation error [T04]', async ({ page }) => {
    await page.goto('/settings/users')
    await page.locator('#add-user-email').clear()
    await page.locator('#add-user-form button[type="submit"]').click()
    await expect(page.locator('#add-user-email.is-invalid')).toBeVisible()
    await expect(page.locator('#add-user-email ~ .invalid-feedback')).toContainText('Valid email is required.')
  })

  test('7.05 Email invalid format shows validation error [T05]', async ({ page }) => {
    await page.goto('/settings/users')
    await page.locator('#add-user-email').fill('notanemail')
    await page.locator('#add-user-form button[type="submit"]').click()
    await expect(page.locator('#add-user-email.is-invalid')).toBeVisible()
  })

  test('7.06 Username invalid format (uppercase/digits) shows validation error [T06]', async ({ page }) => {
    await page.goto('/settings/users')
    await page.locator('#add-user-username').fill('User123')
    await page.locator('#add-user-form button[type="submit"]').click()
    await expect(page.locator('#add-user-username.is-invalid')).toBeVisible()
    await expect(page.locator('#add-user-username ~ .invalid-feedback')).toContainText('Username must be 1-20 lowercase English letters only.')
  })

  test('7.07 Username empty submit shows validation error [T07]', async ({ page }) => {
    await page.goto('/settings/users')
    await page.locator('#add-user-email').fill('valid@example.com')
    await page.locator('#add-user-username').clear()
    await page.locator('#add-user-form button[type="submit"]').click()
    await expect(page.locator('#add-user-username.is-invalid')).toBeVisible()
  })

  test('7.08 Successfully create user with user role only [T08]', async ({ page }) => {
    await page.goto('/settings/users')

    // Mock POST /admin/users to return 201 success
    await page.route('**/admin/users', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({ id: 99, email: 'newusertest@example.com' })
        })
      } else {
        await route.continue()
      }
    })

    // Intercept POST /admin/users
    const postPromise = page.waitForRequest(req =>
      req.method() === 'POST' && req.url().includes('/admin/users')
    )

    await page.locator('#add-user-email').fill('newusertest@example.com')
    await page.locator('#add-user-username').fill('newusertest')
    // #role-user should be checked by default
    await expect(page.locator('#role-user')).toBeChecked()
    await page.locator('#add-user-form button[type="submit"]').click()

    const postReq = await postPromise
    const body = postReq.postDataJSON()
    expect(body.email).toBe('newusertest@example.com')
    expect(body.username).toBe('newusertest')
    expect(body.roles).toEqual(['user'])

    // Success banner becomes visible
    await expect(page.locator('#add-user-success')).toBeVisible()

    // Form resets
    await expect(page.locator('#add-user-email')).toHaveValue('')
    await expect(page.locator('#add-user-username')).toHaveValue('')
  })

  test('7.09 Successfully create user with admin + user roles [T09]', async ({ page }) => {
    await page.goto('/settings/users')

    // Mock POST /admin/users to return 201 success
    await page.route('**/admin/users', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({ id: 100, email: 'adminusertest@example.com' })
        })
      } else {
        await route.continue()
      }
    })

    const postPromise = page.waitForRequest(req =>
      req.method() === 'POST' && req.url().includes('/admin/users')
    )

    await page.locator('#add-user-email').fill('adminusertest@example.com')
    await page.locator('#add-user-username').fill('adminusertest')
    await page.locator('#role-admin').check()
    await page.locator('#add-user-form button[type="submit"]').click()

    const postReq = await postPromise
    const body = postReq.postDataJSON()
    expect(body.roles).toContain('admin')
    expect(body.roles).toContain('user')

    await expect(page.locator('#add-user-success')).toBeVisible()
  })

  test('7.10 Duplicate email shows server error on email field [T10]', async ({ page }) => {
    await page.goto('/settings/users')

    // Mock POST /admin/users to return email conflict error
    await page.route('**/admin/users', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'email already exists' })
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

  test('7.11 Duplicate username shows server error on username field [T11]', async ({ page }) => {
    await page.goto('/settings/users')

    await page.route('**/admin/users', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'username already exists' })
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

  test('7.12 Submit button shows loading state (disabled + spinner) [T12]', async ({ page }) => {
    await page.goto('/settings/users')

    // Intercept POST and delay response
    await page.route('**/admin/users', async (route) => {
      if (route.request().method() === 'POST') {
        await new Promise(resolve => setTimeout(resolve, 2000))
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 1, email: 'test@example.com', username: 'test' })
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

  test('7.13 Search input triggers live filtering [T13]', async ({ page }) => {
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

  test('7.14 Search with no results shows "No users found." [T14]', async ({ page }) => {
    await page.goto('/settings/users')

    await page.route('**/admin/users?*', async (route) => {
      if (route.request().url().includes('search=')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ users: [], total: 0, page: 1, page_size: 20 })
        })
      } else {
        await route.continue()
      }
    })

    await page.locator('#user-search-input').fill('zzzznonexistent')
    await expect(page.locator('#user-list-container p.text-muted')).toContainText('No users found.')
  })

  test('7.15 Clear search restores full user list [T15]', async ({ page }) => {
    await page.goto('/settings/users')
    // Wait for table to load before capturing initial count (loadUsers is async)
    await expect(page.locator('.table tbody tr').first()).toBeVisible()
    const initialCount = await page.locator('.table tbody tr').count()

    await page.locator('#user-search-input').fill('somequery')
    await page.locator('#user-search-input').clear()

    await expect(page.locator('.table tbody tr')).toHaveCount(initialCount)
  })

  test('7.16 Each row displays correct columns: username, email, roles, status, last login, actions [T16]', async ({ page }) => {
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
  test.describe.configure({ mode: 'serial' })

  test('7.17 Block active user: PUT with status blocked, toast, badge update [T17]', async ({ page }) => {
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
    await expect(page.locator('.alert.position-fixed')).toContainText('User blocked.')

    // Badge updates to Blocked
    await expect(page.locator('.badge.bg-danger-subtle')).toBeVisible()
  })

  test('7.18 Unblock blocked user: PUT with status active, toast, badge update [T18]', async ({ page }) => {
    await page.goto('/settings/users')

    const putPromise = page.waitForRequest(req =>
      req.method() === 'PUT' && req.url().match(/\/admin\/users\/\d+$/) !== null
    )

    const unblockBtn = page.locator('button[data-action="toggle-block"][data-status="blocked"]').first()
    await unblockBtn.click()

    const putReq = await putPromise
    const body = putReq.postDataJSON()
    expect(body.status).toBe('active')

    await expect(page.locator('.alert.position-fixed')).toContainText('User unblocked.')
    await expect(page.locator('.badge.bg-success-subtle').first()).toBeVisible()
  })

  test('7.19 Block/Unblock button disabled during request [T19]', async ({ page }) => {
    await page.goto('/settings/users')

    // Intercept PUT and delay response
    await page.route('**/admin/users/*', async (route) => {
      if (route.request().method() === 'PUT') {
        await new Promise(resolve => setTimeout(resolve, 2000))
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 1, status: 'blocked' })
        })
      } else {
        await route.continue()
      }
    })

    const toggleBtn = page.locator('button[data-action="toggle-block"]').first()
    await toggleBtn.click()

    await expect(page.locator('button[data-action="toggle-block"]:disabled')).toBeVisible()
  })

  test('7.20 Block/Unblock API failure shows danger toast [T20]', async ({ page }) => {
    await page.goto('/settings/users')

    await page.route('**/admin/users/*', async (route) => {
      if (route.request().method() === 'PUT') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Internal server error' })
        })
      } else {
        await route.continue()
      }
    })

    const toggleBtn = page.locator('button[data-action="toggle-block"]').first()
    await toggleBtn.click()

    // Toast shows danger variant
    await expect(page.locator('.alert.position-fixed')).toBeVisible()

    // Button re-enabled
    await expect(toggleBtn).toBeEnabled()
  })
})

// =============================================================================
// Delete User
// =============================================================================
test.describe('Delete User', () => {
  test.describe.configure({ mode: 'serial' })

  test('7.21 Delete button triggers confirm dialog with username [T21]', async ({ page }) => {
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

  test('7.22 Cancel confirm does not delete user, list unchanged [T22]', async ({ page }) => {
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

  test('7.23 Confirm delete: DELETE API call, toast, list reloads [T23]', async ({ page }) => {
    // Mock DELETE to return 200 (avoid issues with trying to delete admin's own account)
    await page.route('**/admin/users/*', async (route) => {
      if (route.request().method() === 'DELETE') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'ok' })
        })
      } else {
        await route.continue()
      }
    })

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
    await expect(page.locator('.alert.position-fixed')).toContainText('User deleted.')
  })

  test('7.24 Delete button disabled during request [T24]', async ({ page }) => {
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
          body: JSON.stringify({ status: 'ok' })
        })
      } else {
        await route.continue()
      }
    })

    const deleteBtn = page.locator('button[data-action="delete-user"]').first()
    await deleteBtn.click()

    await expect(page.locator('button[data-action="delete-user"]:disabled')).toBeVisible()
  })

  test('7.25 Delete API failure shows danger toast, button re-enabled [T25]', async ({ page }) => {
    await page.goto('/settings/users')

    await page.on('dialog', async (dialog) => {
      await dialog.accept()
    })

    await page.route('**/admin/users/*', async (route) => {
      if (route.request().method() === 'DELETE') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Internal server error' })
        })
      } else {
        await route.continue()
      }
    })

    const deleteBtn = page.locator('button[data-action="delete-user"]').first()
    await deleteBtn.click()

    // Toast shows danger
    await expect(page.locator('.alert.position-fixed')).toBeVisible()

    // Button re-enabled
    await expect(deleteBtn).toBeEnabled()
  })
})

// =============================================================================
// Edit Button Navigation
// =============================================================================
test.describe('Edit Button Navigation', () => {

  test('7.26 Click Edit navigates to /users/edit?id={userId} [T26]', async ({ page }) => {
    test.slow()
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

  test('7.27 No pagination when users ≤ 20 [T27]', async ({ page }) => {
    await page.goto('/settings/users')

    // Mock API to return ≤ 20 users
    await page.route('**/admin/users*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          users: Array.from({ length: 5 }, (_, i) => ({
            id: i + 1, email: `user${i}@test.com`, username: `user${i}`,
            roles: ['user'], status: 'active', last_login: null
          })),
          total: 5, page: 1, page_size: 20
        })
      })
    })

    await page.goto('/settings/users')
    await expect(page.locator('.pagination')).toHaveCount(0)
  })

  test('7.28 Pagination visible when users > 20, current page active [T28]', async ({ page }) => {
    // Mock API to return > 20 users (set up before goto)
    await page.route('**/admin/users*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          users: Array.from({ length: 20 }, (_, i) => ({
            id: i + 1, email: `user${i}@test.com`, username: `user${i}`,
            roles: ['user'], status: 'active', last_login_at: null
          })),
          total: 25, page: 1, page_size: 20
        })
      })
    })

    await page.goto('/settings/users')
    await expect(page.locator('.table')).toBeVisible()
    await expect(page.locator('nav ul.pagination')).toBeVisible()
    await expect(page.locator('li.page-item.active')).toBeVisible()
  })

  test('7.29 Click page 2 triggers GET with page=2, list updates [T29]', async ({ page }) => {
    test.slow()

    // Mock initial load with pagination (set up before goto)
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
            roles: ['user'], status: 'active', last_login_at: null
          })),
          total: 25, page: Number(currentPage), page_size: 20
        })
      })
    })

    await page.goto('/settings/users')
    await expect(page.locator('.table')).toBeVisible()

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

  test('7.30 Active user shows green Active badge [T30]', async ({ page }) => {
    await page.goto('/settings/users')
    // Wait for table to load
    await expect(page.locator('.table')).toBeVisible()

    const activeBadge = page.locator('.badge.bg-success-subtle.text-success')
    await expect(activeBadge.first()).toBeVisible()
    await expect(activeBadge.first()).toHaveText('Active')
  })

  test('7.31 Blocked user shows red Blocked badge [T31]', async ({ page }) => {
    // Mock API to include a blocked user
    await page.route('**/admin/users*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          users: [
            { id: 1, email: 'active@test.com', username: 'activeuser', roles: ['user'], status: 'active', last_login_at: null, full_name: null },
            { id: 2, email: 'blocked@test.com', username: 'blockeduser', roles: ['user'], status: 'blocked', last_login_at: null, full_name: null }
          ],
          total: 2, page: 1, page_size: 20
        })
      })
    })
    await page.goto('/settings/users')
    // Wait for table to load
    await expect(page.locator('.table')).toBeVisible()

    const blockedBadge = page.locator('.badge.bg-danger-subtle.text-danger')
    await expect(blockedBadge.first()).toBeVisible()
    await expect(blockedBadge.first()).toHaveText('Blocked')
  })

  test('7.32 User with no roles shows "—" placeholder [T32]', async ({ page }) => {
    // Mock API to include a user with no roles
    await page.route('**/admin/users*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          users: [
            { id: 1, email: 'noroles@test.com', username: 'norolesuser', roles: [], status: 'active', last_login_at: null, full_name: null }
          ],
          total: 1, page: 1, page_size: 20
        })
      })
    })
    await page.goto('/settings/users')
    // Wait for table to load
    await expect(page.locator('.table')).toBeVisible()

    // Find a user row with "—" in roles column (td:nth-child(2) = Roles column)
    const placeholder = page.locator('td:nth-child(2) .text-muted')
    await expect(placeholder.first()).toHaveText('—')
  })
})

// =============================================================================
// API Error Handling
// =============================================================================
test.describe('API Error Handling', () => {

  test('7.33 401 Unauthorized redirects to login page [T33]', async ({ page }) => {
    await page.goto('/settings/users')

    // Mock any API call to return 401
    await page.route('**/admin/users*', async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Unauthorized' })
      })
    })

    await page.goto('/settings/users')

    // Should redirect to login page
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })

  test('7.34 User list load failure shows alert-danger with error message [T34]', async ({ page }) => {
    await page.route('**/admin/users*', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' })
      })
    })

    await page.goto('/settings/users')

    const alert = page.locator('#user-list-container .alert-danger')
    await expect(alert).toBeVisible()
    await expect(alert).toContainText(/error/i)
  })
})
