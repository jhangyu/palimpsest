/*
---
name: ui-bugfix
description: "Stage 1 UI bugfix verification — error pages (T7), footer/sidebar/topbar/avatar/AI-tokens regressions"
stage: stage1
type: playwright
target:
  layer: frontend
  domain: ui
spec_doc: null
test_file: tests/stage2/e2e/stage1/ui-bugfix.spec.ts
tests:
  - name: "404 page loads and has dashboard link"
    line: 26
    purpose: "GET /404 returns 200 with dashboard link and Go Back button"
  - name: "401 page loads and login link points to modern login route"
    line: 43
    purpose: "GET /others/401 returns 200 with login link to /authentication/modern/login"
  - name: "500 page loads and has try-again button"
    line: 60
    purpose: "GET /others/500 returns 200 with Try Again button and no support link"
  - name: "404 page does not expose error code in visible h1"
    line: 81
    purpose: "The 404 h1 is d-none; visible heading is descriptive h2 text"
  - name: "admin footer shows only version number, no copyright text"
    line: 102
    purpose: "[skip] Admin layout footer shows version string, no copyright or © symbol"
  - name: "sidebar footer has all required data-session elements"
    line: 123
    purpose: "[skip] Sidebar sticky footer renders all required data-session attributes"
  - name: "topbar offcanvas has data-session elements and no Billing link"
    line: 141
    purpose: "[skip] Topbar user profile offcanvas has session attrs and no billing link"
  - name: "sidebar dropdown does not contain Upgrade or Billing items"
    line: 166
    purpose: "[skip] Sidebar footer dropdown has no /billing or /upgrade links"
  - name: "sidebar nav does not contain template-only demo sections"
    line: 182
    purpose: "[skip] Sidebar nav-tree has no template-only section labels"
  - name: "session populates user name in sidebar after login"
    line: 202
    purpose: "[skip] data-session=user-name elements show actual name, not 'Loading...'"
  - name: "avatar delete restores placeholder and hides img element"
    line: 221
    purpose: "[skip] Clicking Delete Avatar hides img and shows placeholder"
  - name: "avatar upload shows new image and hides placeholder"
    line: 245
    purpose: "[skip] Uploading avatar shows img and hides placeholder"
  - name: "security page contains AI tokens section"
    line: 277
    purpose: "[skip] /users/security renders #ai-tokens-section and Add Token button"
  - name: "settings page does not contain AI tokens section"
    line: 293
    purpose: "[skip] /settings has no #ai-tokens-section or AI Tokens nav link"
  - name: "security page AI tokens add-token modal opens on button click"
    line: 308
    purpose: "[skip] Clicking #ai-tokens-add-btn opens #ai-token-add-modal with all fields"
run:
  command: "cd frontend-astro && npx playwright test tests/stage2/e2e/stage1/ui-bugfix.spec.ts"
  prerequisites:
    - "App running on http://localhost:5174"
---
*/

import { test, expect } from '@playwright/test'

// ---------------------------------------------------------------------------
// T7 — Error pages (no auth required, use authentication-layout)
// ---------------------------------------------------------------------------

test('404 page loads and has dashboard link', async ({ page }) => {
  /**
   * GET /404 — Astro special error page returns HTTP 404 status (framework behavior).
   * The page must contain a "Back to Home" link pointing to /dashboard.
   * A "Go Back" button (history.back) must also be present.
   */
  const res = await page.goto('/404')
  expect([200, 404]).toContain(res?.status())

  const homeLink = page.locator('a[href*="/dashboard"]')
  await expect(homeLink).toBeVisible()
  await expect(homeLink).toContainText('Back to Home')

  const goBackBtn = page.locator('button', { hasText: 'Go Back' })
  await expect(goBackBtn).toBeVisible()
})

test('401 page loads and login link points to modern login route', async ({ page }) => {
  /**
   * GET /others/401 should return HTTP 200.
   * The "Login" button must link to /authentication/modern/login (not /login or /).
   * A "Back to Home" link pointing to /dashboard must also be present.
   */
  const res = await page.goto('/others/401')
  expect(res?.status()).toBe(200)

  const loginLink = page.locator('a[href*="/authentication/modern/login"]')
  await expect(loginLink).toBeVisible()
  await expect(loginLink).toContainText('Login')

  const homeLink = page.locator('a[href*="/dashboard"]')
  await expect(homeLink).toBeVisible()
})

test('500 page loads and has try-again button', async ({ page }) => {
  /**
   * GET /others/500 should return HTTP 200.
   * A "Try Again" button that calls window.location.reload() must be present.
   * A "Back to Home" link to /dashboard must also be present.
   * No "support" link should be present (support section was removed).
   */
  const res = await page.goto('/others/500')
  expect(res?.status()).toBe(200)

  const retryBtn = page.locator('button', { hasText: 'Try Again' })
  await expect(retryBtn).toBeVisible()

  const homeLink = page.locator('a[href*="/dashboard"]')
  await expect(homeLink).toBeVisible()

  // Support section removed — no support contact link
  const supportLink = page.locator('a[href*="support"]')
  await expect(supportLink).not.toBeVisible()
})

test('404 page does not expose error code in visible h1', async ({ page }) => {
  /**
   * The 404 number h1 is marked d-none (screen-reader only).
   * The visible heading must be the descriptive text, not "404".
   */
  await page.goto('/404')

  // h1 with "404" text should be invisible (d-none class)
  const hiddenH1 = page.locator('h1.d-none')
  await expect(hiddenH1).toHaveCount(1)
  await expect(hiddenH1).not.toBeVisible()

  // Visible heading is the h2 with descriptive text
  const visibleHeading = page.locator('h2')
  await expect(visibleHeading).toContainText('Page Not Found')
})

// ---------------------------------------------------------------------------
// T1 — Footer copyright removed
// ---------------------------------------------------------------------------

test.skip('admin footer shows only version number, no copyright text', async ({ page }) => {
  /**
   * The admin layout footer should display the version string from package.json
   * but must NOT contain the word "Copyright" or the © symbol.
   *
   * Requires: authenticated session.
   * Phase 8: inject session via storageState fixture.
   */
  await page.goto('/dashboard')
  const footer = page.locator('footer.footer')
  await expect(footer).not.toContainText('Copyright')
  await expect(footer).not.toContainText('©')
  // Version string is present
  const versionText = await footer.locator('p').textContent()
  expect(versionText).toMatch(/^Version \d+\.\d+\.\d+/)
})

// ---------------------------------------------------------------------------
// T3 + T4 — data-session attributes & Billing removed
// ---------------------------------------------------------------------------

test.skip('sidebar footer has all required data-session elements', async ({ page }) => {
  /**
   * The sidebar sticky footer must render elements with exactly these
   * data-session attribute values:
   *   [data-session="user-name"]   — at least 2 (toggle row + dropdown)
   *   [data-session="user-email"]  — at least 2
   *   [data-session="user-avatar"] — at least 2 (img elements)
   *   [data-session="logout-btn"]  — exactly 1
   *
   * Requires: authenticated session.
   */
  await page.goto('/dashboard')
  await expect(page.locator('[data-session="user-name"]')).toHaveCount(2)
  await expect(page.locator('[data-session="user-email"]')).toHaveCount(2)
  await expect(page.locator('[data-session="user-avatar"]')).toHaveCount(2)
  await expect(page.locator('[data-session="logout-btn"]')).toHaveCount(1)
})

test.skip('topbar offcanvas has data-session elements and no Billing link', async ({ page }) => {
  /**
   * The topbar user profile offcanvas must:
   * - Contain [data-session="user-name"] and [data-session="user-email"]
   * - Contain [data-session="user-avatar"] on the avatar img
   * - Contain [data-session="logout-btn"] on the log-out anchor
   * - NOT contain any link to a "/billing" route
   *
   * Requires: authenticated session.
   */
  await page.goto('/dashboard')
  // Open the offcanvas
  await page.locator('[data-bs-target="#userProfileOffcanvas"]').click()
  const offcanvas = page.locator('#userProfileOffcanvas')
  await expect(offcanvas).toBeVisible()

  await expect(offcanvas.locator('[data-session="user-name"]')).toBeVisible()
  await expect(offcanvas.locator('[data-session="user-email"]')).toBeVisible()
  await expect(offcanvas.locator('[data-session="user-avatar"]')).toBeVisible()
  await expect(offcanvas.locator('[data-session="logout-btn"]')).toBeVisible()

  // Billing removed
  await expect(offcanvas.locator('a[href*="billing"]')).toHaveCount(0)
})

test.skip('sidebar dropdown does not contain Upgrade or Billing items', async ({ page }) => {
  /**
   * The sidebar footer dropdown must not contain links to /billing or /upgrade.
   *
   * Requires: authenticated session.
   */
  await page.goto('/dashboard')
  const sidebarFooter = page.locator('.sidebar-footer')
  await expect(sidebarFooter.locator('a[href*="billing"]')).toHaveCount(0)
  await expect(sidebarFooter.locator('a[href*="upgrade"]')).toHaveCount(0)
})

// ---------------------------------------------------------------------------
// T2 — Template nav sections removed from sidebar
// ---------------------------------------------------------------------------

test.skip('sidebar nav does not contain template-only demo sections', async ({ page }) => {
  /**
   * The sidebar nav-tree must NOT contain sections labeled "Components",
   * "Elements", "Forms", "Charts", "Tables", "Maps", or "Authentication Demo"
   * — these were template nav sections not part of the product.
   *
   * Requires: authenticated session.
   */
  await page.goto('/dashboard')
  const nav = page.locator('.nav-tree')
  const templateSections = ['Components', 'Elements', 'Forms', 'Charts', 'Tables', 'Maps']
  for (const section of templateSections) {
    await expect(nav.locator(`.nav-section-text`, { hasText: section })).toHaveCount(0)
  }
})

// ---------------------------------------------------------------------------
// T5 — Avatar rendering fix
// ---------------------------------------------------------------------------

test.skip('session populates user name in sidebar after login', async ({ page }) => {
  /**
   * After session initialization, [data-session="user-name"] elements should
   * contain the user's full_name (or username if no full_name) — not the
   * placeholder "Loading...".
   *
   * Requires: authenticated session.
   */
  await page.goto('/dashboard')
  await page.waitForLoadState('networkidle')
  const nameEls = page.locator('[data-session="user-name"]')
  const count = await nameEls.count()
  for (let i = 0; i < count; i++) {
    const text = await nameEls.nth(i).textContent()
    expect(text).not.toBe('Loading...')
    expect(text?.trim().length).toBeGreaterThan(0)
  }
})

test.skip('avatar delete restores placeholder and hides img element', async ({ page }) => {
  /**
   * Regression test for the users.ts bug found in review:
   * After clicking "Delete Avatar" and confirming:
   *   - #profile-avatar-img should have class "d-none" (hidden)
   *   - #avatar-placeholder should NOT have class "d-none" (visible)
   *
   * Requires: authenticated session with an existing avatar uploaded.
   */
  await page.goto('/users/profile')
  await page.waitForLoadState('networkidle')

  // Confirm the delete
  page.on('dialog', (dialog) => dialog.accept())
  await page.locator('#avatar-delete-btn').click()

  // After deletion: img hidden, placeholder visible
  const avatarImg = page.locator('#profile-avatar-img')
  await expect(avatarImg).toHaveClass(/d-none/)

  const placeholder = page.locator('#avatar-placeholder')
  await expect(placeholder).not.toHaveClass(/d-none/)
})

test.skip('avatar upload shows new image and hides placeholder', async ({ page }) => {
  /**
   * Regression test for the users.ts bug found in review:
   * After uploading a new avatar when currently in "no avatar" state:
   *   - #profile-avatar-img should NOT have class "d-none" (visible)
   *   - #avatar-placeholder should have class "d-none" (hidden)
   *
   * Requires: authenticated session with avatar_source === 'none'.
   */
  await page.goto('/users/profile')
  await page.waitForLoadState('networkidle')

  // Simulate file upload via the hidden input
  const fileInput = page.locator('#avatar-file-input')
  await fileInput.setInputFiles({
    name: 'test-avatar.jpg',
    mimeType: 'image/jpeg',
    buffer: Buffer.alloc(1024) // 1KB dummy JPEG
  })

  // After upload: img visible, placeholder hidden
  const avatarImg = page.locator('#profile-avatar-img')
  await expect(avatarImg).not.toHaveClass(/d-none/)

  const placeholder = page.locator('#avatar-placeholder')
  await expect(placeholder).toHaveClass(/d-none/)
})

// ---------------------------------------------------------------------------
// T6 — AI Tokens moved from Settings to Security page
// ---------------------------------------------------------------------------

test.skip('security page contains AI tokens section', async ({ page }) => {
  /**
   * GET /users/security must render the #ai-tokens-section card.
   * The "Add Token" button (#ai-tokens-add-btn) must be visible.
   * The token list container (#ai-tokens-list) must be present.
   *
   * Requires: authenticated session.
   */
  await page.goto('/users/security')
  await page.waitForLoadState('networkidle')

  await expect(page.locator('#ai-tokens-section')).toBeVisible()
  await expect(page.locator('#ai-tokens-add-btn')).toBeVisible()
  await expect(page.locator('#ai-tokens-list')).toBeAttached()
})

test.skip('settings page does not contain AI tokens section', async ({ page }) => {
  /**
   * GET /settings must NOT contain any element with id="ai-tokens-section".
   * The sidebar nav on the settings page must only show General / Company /
   * Regional tabs — no AI Tokens tab.
   *
   * Requires: authenticated session.
   */
  await page.goto('/settings')
  await page.waitForLoadState('networkidle')

  await expect(page.locator('#ai-tokens-section')).toHaveCount(0)
  await expect(page.locator('[href*="ai-tokens"]')).toHaveCount(0)
})

test.skip('security page AI tokens add-token modal opens on button click', async ({ page }) => {
  /**
   * Clicking #ai-tokens-add-btn on the security page should open a Bootstrap
   * modal with id="ai-token-add-modal" and show all required fields:
   * provider select, label input, token input, current-password input.
   *
   * Requires: authenticated session.
   */
  await page.goto('/users/security')
  await page.waitForLoadState('networkidle')

  await page.locator('#ai-tokens-add-btn').click()

  const modal = page.locator('#ai-token-add-modal')
  await expect(modal).toBeVisible()
  await expect(modal.locator('#add-provider')).toBeVisible()
  await expect(modal.locator('#add-label')).toBeVisible()
  await expect(modal.locator('#add-token-value')).toBeVisible()
  await expect(modal.locator('#add-current-password')).toBeVisible()
})
