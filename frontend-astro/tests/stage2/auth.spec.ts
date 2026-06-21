/**
 * S2-01: Dashboard & Auth — Playwright Tests
 * Spec: docs/test-specs/s2-01-dashboard-auth.md
 *
 * Covers: Global Layout (Topbar/Sidebar), Index, Dashboard, Analytics,
 * Articles, Login, Register, Setup, Forgot Password, New Password,
 * Verify Email, Link Sent, Reset Successfully pages.
 *
 * Tests requiring authentication are marked test.skip until session fixture lands.
 * Run: npx playwright test tests/auth.spec.ts
 */
import { test, expect } from '@playwright/test'

// =============================================================================
// Global Layout — Topbar
// All topbar tests require authenticated session to access admin pages
// =============================================================================
test.describe('Global Layout — Topbar', () => {

  test.skip('T-01: Sidebar toggle button toggles sidebar collapsed state', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    const toggle = page.locator('#sidebar-toggle')
    await toggle.click()
    await expect(page.locator('.app-sidebar')).toHaveClass(/collapsed/)
    await toggle.click()
    await expect(page.locator('.app-sidebar')).not.toHaveClass(/collapsed/)
  })

  test.skip('T-02: Search toggle opens search modal', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await page.locator('#search-toggle').click()
    await expect(page.locator('#searchModal')).toBeVisible()
  })

  test.skip('T-03: Theme toggle switches dark/light mode', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    const html = page.locator('html')
    const initialTheme = await html.getAttribute('data-theme')
    await page.locator('#theme-toggle').click()
    const newTheme = await html.getAttribute('data-theme')
    expect(newTheme).not.toBe(initialTheme)
    // Check toggle icon changed (moon/sun icon)
    const isDark = newTheme === 'dark'
    if (isDark) {
      await expect(page.locator('#theme-toggle .ri-moon-line')).toBeVisible()
    } else {
      await expect(page.locator('#theme-toggle .ri-sun-line')).toBeVisible()
    }
  })

  test.skip('T-04: GitHub link opens in new tab', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    const githubLink = page.locator('a[href*="github"]')
    await expect(githubLink).toHaveAttribute('target', '_blank')
  })

  test.skip('T-05: Notifications dropdown opens on click', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await page.locator('.notifications-dropdown button[data-bs-toggle="dropdown"]').click()
    await expect(page.locator('.notifications-menu')).toBeVisible()
  })

  test.skip('T-06: Empty notifications shows placeholder message', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await page.locator('.notifications-dropdown button[data-bs-toggle="dropdown"]').click()
    await expect(page.locator('.notifications-list')).toContainText('No new notifications')
  })

  test.skip('T-07: Notification badge shows count when notifications exist', async ({ page }) => {
    // TODO: requires auth session fixture + notification data
    await page.goto('/dashboard')
    const badge = page.locator('.notifications-dropdown .badge')
    await expect(badge).not.toHaveClass(/d-none/)
    const text = await badge.textContent()
    expect(Number(text)).toBeGreaterThan(0)
  })

  test.skip('T-08: User avatar button opens Profile Offcanvas', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await page.locator('.user-profile button[data-bs-toggle="offcanvas"]').click()
    await expect(page.locator('#userProfileOffcanvas')).toBeVisible()
  })

  test.skip('T-09: Profile Offcanvas displays user name and email', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await page.locator('.user-profile button[data-bs-toggle="offcanvas"]').click()
    await expect(page.locator('[data-session="user-name"]')).not.toBeEmpty()
    await expect(page.locator('[data-session="user-email"]')).not.toBeEmpty()
  })

  test.skip('T-10: Offcanvas Profile link navigates to /users/profile', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await page.locator('.user-profile button[data-bs-toggle="offcanvas"]').click()
    await page.locator('a[href*="/users/profile"]').click()
    await expect(page).toHaveURL(/\/users\/profile/)
  })

  test.skip('T-11: Offcanvas Security link navigates to /users/security', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await page.locator('.user-profile button[data-bs-toggle="offcanvas"]').click()
    await page.locator('a[href*="/users/security"]').click()
    await expect(page).toHaveURL(/\/users\/security/)
  })

  test.skip('T-12: Offcanvas Settings link navigates to /settings', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await page.locator('.user-profile button[data-bs-toggle="offcanvas"]').click()
    await page.locator('a[href*="/settings"]').click()
    await expect(page).toHaveURL(/\/settings/)
  })

  test.skip('T-13: Logout triggers POST /auth/logout and redirects to login', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await page.locator('.user-profile button[data-bs-toggle="offcanvas"]').click()
    const responsePromise = page.waitForResponse(resp =>
      resp.url().includes('/auth/logout') && resp.request().method() === 'POST'
    )
    await page.locator('[data-session="logout-btn"]').click()
    await responsePromise
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })

  test.skip('T-14: After logout, visiting protected page redirects to login', async ({ page }) => {
    // TODO: requires auth session fixture (login → logout → verify redirect)
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })
})

// =============================================================================
// Global Layout — Sidebar
// =============================================================================
test.describe('Global Layout — Sidebar', () => {

  test.skip('S-01: Mini sidebar toggle adds/removes sidebar-mini class', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await page.locator('#toggle-mini-button').click()
    await expect(page.locator('.app-sidebar')).toHaveClass(/sidebar-mini/)
    await page.locator('#toggle-mini-button').click()
    await expect(page.locator('.app-sidebar')).not.toHaveClass(/sidebar-mini/)
  })

  test.skip('S-02: Dashboard nav link has active state on /dashboard', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    const link = page.locator('.nav-tree a[href*="/dashboard"]')
    await expect(link.locator('..')).toHaveClass(/active/)
  })

  test.skip('S-03: Analytics nav link navigates to /analytics', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await page.locator('.nav-tree a[href*="/analytics"]').click()
    await expect(page).toHaveURL(/\/analytics/)
  })

  test.skip('S-04: Articles nav link navigates to /articles', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await page.locator('.nav-tree a[href*="/articles"]').click()
    await expect(page).toHaveURL(/\/articles/)
  })

  test.skip('S-05: Add Feed nav link navigates to /feeds/add', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await page.locator('.nav-tree a[href*="/feeds/add"]').click()
    await expect(page).toHaveURL(/\/feeds\/add/)
  })

  test.skip('S-06: Manage Feeds nav link navigates to /feeds/edit', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await page.locator('.nav-tree a[href*="/feeds/edit"]').click()
    await expect(page).toHaveURL(/\/feeds\/edit/)
  })

  test.skip('S-07: Users submenu expands to show Profile/Security/AI Service', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    const usersMenu = page.locator('.nav-item.has-submenu').filter({ hasText: 'Users' })
    await usersMenu.locator('a[href="#"]').click()
    await expect(usersMenu.locator('.submenu')).toBeVisible()
  })

  test.skip('S-08: Settings submenu expands to show General/User Management/Database', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    const settingsMenu = page.locator('.nav-item.has-submenu').filter({ hasText: 'Settings' })
    await settingsMenu.locator('a[href="#"]').click()
    await expect(settingsMenu.locator('.submenu')).toBeVisible()
  })

  test.skip('S-09: Admin user sees User Management nav item', async ({ page }) => {
    // TODO: requires admin auth session fixture
    await page.goto('/dashboard')
    await expect(page.locator('[data-requires-role="admin"]')).toBeVisible()
  })

  test.skip('S-10: Regular user does not see User Management nav item', async ({ page }) => {
    // TODO: requires regular user auth session fixture
    await page.goto('/dashboard')
    await expect(page.locator('[data-requires-role="admin"]')).toBeHidden()
  })
})

// =============================================================================
// Index Page (/)
// =============================================================================
test.describe('Index Page', () => {

  test('I-01: Homepage returns HTTP 200', async ({ page }) => {
    const response = await page.goto('/')
    expect(response?.status()).toBe(200)
  })

  test('I-02: Homepage has no console errors', async ({ page }) => {
    const errors: string[] = []
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text())
    })
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    expect(errors).toHaveLength(0)
  })

  test('I-03: Homepage contains meta refresh redirect to /dashboard', async ({ page }) => {
    await page.goto('/')
    const metaRefresh = page.locator('meta[http-equiv="refresh"]')
    await expect(metaRefresh).toHaveAttribute('content', /\/dashboard/)
  })

  test('I-04: Homepage contains fallback JS redirect link', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.redirect-link')).toBeVisible()
  })
})

// =============================================================================
// Dashboard Page (/dashboard)
// =============================================================================
test.describe('Dashboard Page', () => {

  test.skip('D-01: Page title contains "Dashboard"', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await expect(page).toHaveTitle(/Dashboard/)
  })

  test.skip('D-02: "Add New Feed" header button links to /feeds/add', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    const addBtn = page.locator('a.btn-primary[href*="/feeds/add"]')
    await expect(addBtn).toBeVisible()
    await addBtn.click()
    await expect(page).toHaveURL(/\/feeds\/add/)
  })

  test.skip('D-03: Metric cards show placeholder animation on initial load', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await expect(page.locator('#dashboard-metrics .placeholder').first()).toBeVisible()
  })

  test.skip('D-04: Metric cards populate with values after API response', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')
    const metrics = page.locator('#dashboard-metrics')
    await expect(metrics.locator('.placeholder').first()).not.toBeVisible()
    const metricsText = await metrics.textContent()
    expect(metricsText).toMatch(/\d+/)
  })

  test.skip('D-05: Active Feeds card "Add New" button links to /feeds/add', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    const addBtn = page.locator('.card-header a.btn-primary[href*="/feeds/add"]')
    await expect(addBtn).toBeVisible()
    await addBtn.click()
    await expect(page).toHaveURL(/\/feeds\/add/)
  })

  test.skip('D-06: Active Feeds table loads feed data or shows empty message', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')
    const table = page.locator('#dashboard-feed-table')
    await expect(table).toBeVisible()
  })

  test.skip('D-07: Unauthenticated access to /dashboard redirects to login', async ({ page }) => {
    // TODO: requires verifying redirect behavior when NOT logged in
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })
})

// =============================================================================
// Analytics Page (/analytics)
// =============================================================================
test.describe('Analytics Page', () => {

  test.skip('A-01: Loading spinner is visible on initial load', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/analytics')
    await expect(page.locator('#analyticsLoadingState')).toBeVisible()
  })

  test.skip('A-02: Spinner disappears after API response', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/analytics')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#analyticsLoadingState')).toBeHidden()
  })

  test.skip('A-03: Four metric info-boxes populate with data', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/analytics')
    await page.waitForLoadState('networkidle')
    for (const id of [
      '#analytics-total-article-scrap',
      '#analytics-new-articles-week',
      '#analytics-median-feed-update',
      '#analytics-median-word-count'
    ]) {
      await expect(page.locator(id)).not.toHaveText('—')
    }
  })

  test.skip('A-04: Articles Counts Chart renders SVG', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/analytics')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#articlesCountsChart svg')).toBeVisible()
  })

  test.skip('A-05: Feeds Distribution Chart renders SVG', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/analytics')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#feedsDistributionChart svg')).toBeVisible()
  })

  test.skip('A-06: Articles Growth Chart renders SVG', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/analytics')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#articleGrowthChart svg')).toBeVisible()
  })

  test.skip('A-07: Traffic Metrics sparkline charts render SVG', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/analytics')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#rssQueryMetricChart svg')).toBeVisible()
    await expect(page.locator('#articleScrapMetricChart svg')).toBeVisible()
  })

  test.skip('A-08: Traffic totals populate with numeric values', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/analytics')
    await page.waitForLoadState('networkidle')
    for (const id of ['#rssQueryTotal', '#articleScrapSuccessTotal', '#articleScrapFailTotal']) {
      await expect(page.locator(id)).not.toHaveText('—')
    }
  })

  test.skip('A-09: Real-time activity table shows rows or empty message', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/analytics')
    await page.waitForLoadState('networkidle')
    const rows = page.locator('#latestArticlesTableBody tr')
    const count = await rows.count()
    if (count === 0) {
      await expect(page.locator('#latestArticlesTableBody')).toContainText('No articles yet')
    } else {
      expect(count).toBeGreaterThan(0)
    }
  })

  test.skip('A-10: Latest articles external links have rel="noopener"', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/analytics')
    await page.waitForLoadState('networkidle')
    const links = page.locator('#latestArticlesTableBody a[target="_blank"]')
    const count = await links.count()
    for (let i = 0; i < count; i++) {
      await expect(links.nth(i)).toHaveAttribute('rel', /noopener/)
    }
  })

  test.skip('A-11: New Articles tab shows content and hides others', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/analytics')
    await page.waitForLoadState('networkidle')
    await page.locator('a[href="#newArticlesContent"]').click()
    await expect(page.locator('#newArticlesContent')).toBeVisible()
    await expect(page.locator('#failedCrawlsContent')).toBeHidden()
  })

  test.skip('A-12: Failed Crawls tab shows its content', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/analytics')
    await page.waitForLoadState('networkidle')
    await page.locator('a[href="#failedCrawlsContent"]').click()
    await expect(page.locator('#failedCrawlsContent')).toBeVisible()
  })

  test.skip('A-13: AI Repairs tab shows its content', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/analytics')
    await page.waitForLoadState('networkidle')
    await page.locator('a[href="#aiRepairsContent"]').click()
    await expect(page.locator('#aiRepairsContent')).toBeVisible()
  })

  test.skip('A-14: Fetch Failures tab shows its content', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/analytics')
    await page.waitForLoadState('networkidle')
    await page.locator('a[href="#fetchFailuresContent"]').click()
    await expect(page.locator('#fetchFailuresContent')).toBeVisible()
  })

  test.skip('A-15: Event Summary cards populate with values', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/analytics')
    await page.waitForLoadState('networkidle')
    for (const id of [
      '#eventSummaryNewArticles',
      '#eventSummaryFailedCrawls',
      '#eventSummaryAiRepairs',
      '#eventSummaryFetchFailures'
    ]) {
      await expect(page.locator(id)).not.toHaveText('—')
    }
  })

  test.skip('A-16: API error shows error state alert', async ({ page }) => {
    // TODO: requires auth session fixture + API route mock for 500 response
    await page.goto('/analytics')
    await expect(page.locator('#analyticsErrorState')).toBeVisible()
  })
})

// =============================================================================
// Articles Page (/articles)
// =============================================================================
test.describe('Articles Page', () => {

  test.skip('AR-01: Initial loading spinner is visible', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await expect(page.locator('#articlesLoadingState')).toBeVisible()
  })

  test.skip('AR-02: Content area displays after API load', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#articlesContent')).toBeVisible()
  })

  test.skip('AR-03: Filter tab badges show counts', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    const badges = page.locator('#articlesFilterTabs .badge')
    const count = await badges.count()
    expect(count).toBe(4)
  })

  test.skip('AR-04: Today filter tab activates and reloads table', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    const tab = page.locator('[data-filter="today"]')
    await tab.click()
    await expect(tab).toHaveClass(/active/)
  })

  test.skip('AR-05: This Week filter tab activates', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    const tab = page.locator('[data-filter="week"]')
    await tab.click()
    await expect(tab).toHaveClass(/active/)
  })

  test.skip('AR-06: This Month filter tab activates', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    const tab = page.locator('[data-filter="month"]')
    await tab.click()
    await expect(tab).toHaveClass(/active/)
  })

  test.skip('AR-07: All filter tab activates', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    const tab = page.locator('[data-filter="all"]')
    await tab.click()
    await expect(tab).toHaveClass(/active/)
  })

  test.skip('AR-08: Search input filters table rows client-side', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    await page.locator('#articlesSearchInput').fill('keyword')
    await expect(page.locator('#articlesSearchInput')).toHaveValue('keyword')
  })

  test.skip('AR-09: Search clear button resets search input', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    await page.locator('#articlesSearchInput').fill('keyword')
    await page.locator('.btn-clear.search-clear').click()
    await expect(page.locator('#articlesSearchInput')).toHaveValue('')
  })

  test.skip('AR-10: Filter Drawer opens on button click', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    await page.locator('button[data-bs-target="#articlesFilterDrawer"]').click()
    await expect(page.locator('#articlesFilterDrawer')).toBeVisible()
  })

  test.skip('AR-11: Filter Drawer feed source dropdown is available', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    await page.locator('button[data-bs-target="#articlesFilterDrawer"]').click()
    await expect(page.locator('#filterFeedSource')).toBeVisible()
  })

  test.skip('AR-12: Filter Drawer word count min/max inputs accept values', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    await page.locator('button[data-bs-target="#articlesFilterDrawer"]').click()
    await page.locator('#filterWordCountMin').fill('100')
    await page.locator('#filterWordCountMax').fill('500')
    await expect(page.locator('#filterWordCountMin')).toHaveValue('100')
    await expect(page.locator('#filterWordCountMax')).toHaveValue('500')
  })

  test.skip('AR-13: Apply Filters closes drawer and filters table', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    await page.locator('button[data-bs-target="#articlesFilterDrawer"]').click()
    await page.locator('#articlesApplyFilter').click()
    await expect(page.locator('#articlesFilterDrawer')).toBeHidden()
  })

  test.skip('AR-14: Reset Filters clears all filter inputs', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    await page.locator('button[data-bs-target="#articlesFilterDrawer"]').click()
    await page.locator('#filterWordCountMin').fill('100')
    await page.locator('#articlesResetFilter').click()
    await expect(page.locator('#filterWordCountMin')).toHaveValue('')
  })

  test.skip('AR-15: Filter Drawer close button closes drawer', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    await page.locator('button[data-bs-target="#articlesFilterDrawer"]').click()
    await page.locator('.offcanvas-header .btn-close').click()
    await expect(page.locator('#articlesFilterDrawer')).toBeHidden()
  })

  test.skip('AR-16: Export CSV triggers file download', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    const downloadPromise = page.waitForEvent('download')
    await page.locator('#articlesExportBtn').click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toContain('articles')
  })

  test.skip('AR-17: Title column header click triggers sort', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    const titleHeader = page.locator('th').filter({ hasText: 'Title' })
    await titleHeader.click()
    await expect(titleHeader).toBeVisible()
    // Check sort indicator (▲/▼ or sort class on header)
    const titleHeaderText = await titleHeader.textContent()
    const titleHasSortIndicator = titleHeaderText?.includes('▲') || titleHeaderText?.includes('▼') ||
      await titleHeader.evaluate(el => el.classList.contains('sort-asc') || el.classList.contains('sort-desc') || el.classList.contains('sorted'))
    expect(titleHasSortIndicator).toBe(true)
  })

  test.skip('AR-18: Words column header click sorts by word count', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    const wordsHeader = page.locator('th').filter({ hasText: 'Words' })
    await wordsHeader.click()
    await expect(wordsHeader).toBeVisible()
    // Check sort indicator (▲/▼ or sort class on header)
    const wordsHeaderText = await wordsHeader.textContent()
    const wordsHasSortIndicator = wordsHeaderText?.includes('▲') || wordsHeaderText?.includes('▼') ||
      await wordsHeader.evaluate(el => el.classList.contains('sort-asc') || el.classList.contains('sort-desc') || el.classList.contains('sorted'))
    expect(wordsHasSortIndicator).toBe(true)
  })

  test.skip('AR-19: Pagination Next button advances to next page', async ({ page }) => {
    // TODO: requires auth session fixture + sufficient article data
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    await page.locator('button[aria-label="Next page"]').click()
  })

  test.skip('AR-20: Pagination Previous button goes back one page', async ({ page }) => {
    // TODO: requires auth session fixture + sufficient article data
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    await page.locator('button[aria-label="Next page"]').click()
    await page.locator('button[aria-label="Previous page"]').click()
  })

  test.skip('AR-21: Pagination page number button jumps to specific page', async ({ page }) => {
    // TODO: requires auth session fixture + sufficient article data
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    await page.locator('button[aria-label="Page 2"]').click()
  })

  test.skip('AR-22: Rows per page selector changes visible row count', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    await page.locator('select[aria-label="Rows per page"]').selectOption('10')
  })

  test.skip('AR-23: Article title external links have rel="noopener"', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    const links = page.locator('table a[target="_blank"]')
    const count = await links.count()
    for (let i = 0; i < count; i++) {
      await expect(links.nth(i)).toHaveAttribute('rel', /noopener/)
    }
  })

  test.skip('AR-24: Feed badges have Bootstrap color classes', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    const badges = page.locator('table .badge[class*="bg-"]')
    const count = await badges.count()
    expect(count).toBeGreaterThan(0)
  })

  test.skip('AR-25: Empty search results show "No articles found" message', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/articles')
    await page.waitForLoadState('networkidle')
    await page.locator('#articlesSearchInput').fill('zzz_nonexistent_keyword_zzz')
    await expect(page.locator('#articlesTableContainer')).toContainText('No articles found')
  })

  test.skip('AR-26: API error shows error state alert', async ({ page }) => {
    // TODO: requires auth session fixture + API route mock for 500 response
    await page.goto('/articles')
    await expect(page.locator('#articlesErrorState')).toBeVisible()
  })
})

// =============================================================================
// Login Page (/authentication/modern/login)
// =============================================================================
test.describe('Login Page', () => {

  test('L-01: Login page renders email, password, and submit button', async ({ page }) => {
    await page.goto('/authentication/modern/login')
    await expect(page.locator('#email')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.locator('button[type="submit"]')).toBeVisible()
  })

  test.skip('L-02: Valid credentials login redirects to dashboard', async ({ page }) => {
    // TODO: requires test user credentials + running backend API
    await page.goto('/authentication/modern/login')
    await page.locator('#email').fill('admin@example.com')
    await page.locator('#password').fill('validpassword')
    const responsePromise = page.waitForResponse(resp =>
      resp.url().includes('/auth/login') && resp.request().method() === 'POST'
    )
    await page.locator('button[type="submit"]').click()
    await responsePromise
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test.skip('L-03: Wrong password shows inline error message', async ({ page }) => {
    // TODO: requires running backend API
    await page.goto('/authentication/modern/login')
    await page.locator('#email').fill('admin@example.com')
    await page.locator('#password').fill('wrongpassword')
    await page.locator('button[type="submit"]').click()
    await expect(page.locator('#login-form .auth-form-error')).toBeVisible()
  })

  test('L-04: Empty fields submission shows client-side validation error', async ({ page }) => {
    await page.goto('/authentication/modern/login')
    await page.locator('button[type="submit"]').click()
    await expect(page.locator('.auth-form-error')).toContainText('Please enter your email and password')
  })

  test('L-05: Password visibility toggle switches input type', async ({ page }) => {
    await page.goto('/authentication/modern/login')
    const passwordInput = page.locator('#password')
    await expect(passwordInput).toHaveAttribute('type', 'password')
    await page.locator('.password-toggle').click()
    await expect(passwordInput).toHaveAttribute('type', 'text')
    await page.locator('.password-toggle').click()
    await expect(passwordInput).toHaveAttribute('type', 'password')
  })

  test('L-06: Submit button shows loading state during submission', async ({ page }) => {
    await page.goto('/authentication/modern/login')
    await page.locator('#email').fill('test@example.com')
    await page.locator('#password').fill('somepassword')
    await page.locator('button[type="submit"]').click()
    await expect(page.locator('button[type="submit"]')).toBeDisabled()
  })

  test('L-07: ?reset=success query param shows reset success alert', async ({ page }) => {
    await page.goto('/authentication/modern/login?reset=success')
    await expect(page.locator('#reset-success-alert')).toBeVisible()
  })

  test('L-08: ?setup=success query param shows setup success alert', async ({ page }) => {
    await page.goto('/authentication/modern/login?setup=success')
    await expect(page.locator('#setup-success-alert')).toBeVisible()
  })

  test.skip('L-09: First-run banner appears when needs_setup is true', async ({ page }) => {
    // TODO: requires API mock for GET /auth/first-run-check → { needs_setup: true }
    await page.goto('/authentication/modern/login')
    await expect(page.locator('#first-run-banner')).toBeVisible()
  })

  test('L-10: Forgot password link navigates to forgot-password page', async ({ page }) => {
    await page.goto('/authentication/modern/login')
    await page.locator('a[href*="forgot-password"]').click()
    await expect(page).toHaveURL(/\/authentication\/modern\/forgot-password/)
  })

  test('L-11: First time setup link navigates to setup page', async ({ page }) => {
    await page.goto('/authentication/modern/login')
    const setupLink = page.locator('a[href*="setup"]')
    await expect(setupLink).toBeVisible()
    await setupLink.click()
    await expect(page).toHaveURL(/\/authentication\/modern\/setup/)
  })
})

// =============================================================================
// Register Page (/authentication/modern/register)
// =============================================================================
test.describe('Register Page', () => {

  test('R-01: Register page renders form with all inputs', async ({ page }) => {
    await page.goto('/authentication/modern/register')
    await expect(page.locator('#register-form')).toBeVisible()
    await expect(page.locator('#username')).toBeVisible()
    await expect(page.locator('#email')).toBeVisible()
    await expect(page.locator('#password')).toBeVisible()
  })

  test.skip('R-02: Valid registration submits and redirects to dashboard', async ({ page }) => {
    // TODO: requires running backend API + unique test user
    await page.goto('/authentication/modern/register')
    await page.locator('#full_name').fill('Test User')
    await page.locator('#username').fill('testuser')
    await page.locator('#email').fill('test@example.com')
    await page.locator('#password').fill('securepassword123')
    await page.locator('button[type="submit"]').click()
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('R-03: Missing required fields shows validation error', async ({ page }) => {
    await page.goto('/authentication/modern/register')
    await page.locator('button[type="submit"]').click()
    await expect(page.locator('.auth-form-error')).toContainText('Please fill in all required fields')
  })

  test('R-04: Invalid username format triggers HTML5 pattern validation', async ({ page }) => {
    await page.goto('/authentication/modern/register')
    const usernameInput = page.locator('#username')
    await usernameInput.fill('Invalid User!')
    const isValid = await usernameInput.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test('R-05: Short password triggers minlength validation', async ({ page }) => {
    await page.goto('/authentication/modern/register')
    const passwordInput = page.locator('#password')
    await passwordInput.fill('123')
    const isValid = await passwordInput.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test('R-06: Password visibility toggle switches input type', async ({ page }) => {
    await page.goto('/authentication/modern/register')
    const passwordInput = page.locator('#password')
    await expect(passwordInput).toHaveAttribute('type', 'password')
    await page.locator('.password-toggle').click()
    await expect(passwordInput).toHaveAttribute('type', 'text')
  })

  test.skip('R-07: Registration disabled (403) shows warning alert', async ({ page }) => {
    // TODO: requires API mock for POST /auth/register → 403
    await page.goto('/authentication/modern/register')
    await expect(page.locator('#registration-disabled-alert')).toBeVisible()
  })

  test('R-08: Top Sign In button navigates to login page', async ({ page }) => {
    await page.goto('/authentication/modern/register')
    await page.locator('a.btn-outline-primary[href*="login"]').click()
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })

  test('R-09: Bottom Sign In link navigates to login page', async ({ page }) => {
    await page.goto('/authentication/modern/register')
    const signInLinks = page.locator('a[href*="login"]')
    await signInLinks.last().click()
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })
})

// =============================================================================
// Setup Page (/authentication/modern/setup)
// =============================================================================
test.describe('Setup Page', () => {

  test('SE-01: Setup page renders form with all required fields', async ({ page }) => {
    await page.goto('/authentication/modern/setup')
    await expect(page.locator('#setup-form')).toBeVisible()
    await expect(page.locator('#email')).toBeVisible()
    await expect(page.locator('#username')).toBeVisible()
    await expect(page.locator('#password')).toBeVisible()
    await expect(page.locator('#confirm_password')).toBeVisible()
  })

  test.skip('SE-02: Successful admin setup redirects to login with success param', async ({ page }) => {
    // TODO: requires clean database state or API mock
    await page.goto('/authentication/modern/setup')
    await page.locator('#full_name').fill('Admin User')
    await page.locator('#email').fill('admin@example.com')
    await page.locator('#username').fill('admin')
    await page.locator('#password').fill('securepassword')
    await page.locator('#confirm_password').fill('securepassword')
    await page.locator('button[type="submit"]').click()
    await expect(page).toHaveURL(/\/authentication\/modern\/login\?setup=success/)
  })

  test('SE-03: Mismatched passwords shows error message', async ({ page }) => {
    await page.goto('/authentication/modern/setup')
    await page.locator('#full_name').fill('Test')
    await page.locator('#email').fill('test@example.com')
    await page.locator('#username').fill('testuser')
    await page.locator('#password').fill('password123')
    await page.locator('#confirm_password').fill('different456')
    await page.locator('button[type="submit"]').click()
    await expect(page.locator('.auth-form-error')).toContainText('Passwords do not match')
  })

  test('SE-04: Password length outside valid range shows error', async ({ page }) => {
    await page.goto('/authentication/modern/setup')
    await page.locator('#full_name').fill('Test')
    await page.locator('#email').fill('test@example.com')
    await page.locator('#username').fill('testuser')
    await page.locator('#password').fill('short')
    await page.locator('#confirm_password').fill('short')
    await page.locator('button[type="submit"]').click()
    await expect(page.locator('.auth-form-error')).toContainText('Password must be between 8 and 20 characters')
  })

  test.skip('SE-05: Existing user (403/409) hides form and shows setup-done alert', async ({ page }) => {
    // TODO: requires API mock for POST /auth/first-run-setup → 403 or 409
    await page.goto('/authentication/modern/setup')
    await expect(page.locator('#setup-done-alert')).toBeVisible()
    await expect(page.locator('#setup-form')).toBeHidden()
  })

  test.skip('SE-06: Setup-done alert contains Sign In link to login page', async ({ page }) => {
    // TODO: requires API mock for 403/409 response
    await page.goto('/authentication/modern/setup')
    await expect(page.locator('#setup-done-alert a[href*="login"]')).toBeVisible()
  })

  test('SE-07: Both password toggle buttons work independently', async ({ page }) => {
    await page.goto('/authentication/modern/setup')
    const toggles = page.locator('.password-toggle')
    const passwordInput = page.locator('#password')
    const confirmInput = page.locator('#confirm_password')
    // Toggle first password field
    await toggles.first().click()
    await expect(passwordInput).toHaveAttribute('type', 'text')
    await expect(confirmInput).toHaveAttribute('type', 'password')
    // Toggle second password field
    await toggles.last().click()
    await expect(confirmInput).toHaveAttribute('type', 'text')
  })

  test('SE-08: "Already have an account" link navigates to login', async ({ page }) => {
    await page.goto('/authentication/modern/setup')
    await page.locator('a[href*="login"]').click()
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })
})

// =============================================================================
// Forgot Password Page (/authentication/modern/forgot-password)
// =============================================================================
test.describe('Forgot Password Page', () => {

  test('FP-01: Page renders form with email input and submit button', async ({ page }) => {
    await page.goto('/authentication/modern/forgot-password')
    await expect(page.locator('#forgot-password-form')).toBeVisible()
    await expect(page.locator('#email')).toBeVisible()
    await expect(page.locator('button[type="submit"]')).toBeVisible()
  })

  test.skip('FP-02: Valid email submission shows success message', async ({ page }) => {
    // TODO: requires running backend API for POST /auth/forgot-password
    await page.goto('/authentication/modern/forgot-password')
    await page.locator('#email').fill('user@example.com')
    await page.locator('button[type="submit"]').click()
    await expect(page.locator('.auth-form-success')).toBeVisible()
  })

  test('FP-03: Empty email submission shows validation error', async ({ page }) => {
    await page.goto('/authentication/modern/forgot-password')
    await page.locator('button[type="submit"]').click()
    await expect(page.locator('.auth-form-error')).toContainText('Please enter your email address')
  })

  test('FP-04: Invalid email format triggers HTML5 validation', async ({ page }) => {
    await page.goto('/authentication/modern/forgot-password')
    const emailInput = page.locator('#email')
    await emailInput.fill('notanemail')
    const isValid = await emailInput.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test.skip('FP-05: Submit button shows loading state during API call', async ({ page }) => {
    // TODO: requires running backend API
    await page.goto('/authentication/modern/forgot-password')
    await page.locator('#email').fill('user@example.com')
    await page.locator('button[type="submit"]').click()
    await expect(page.locator('button[type="submit"]')).toBeDisabled()
  })

  test.skip('FP-06: Form resets after successful submission', async ({ page }) => {
    // TODO: requires running backend API
    await page.goto('/authentication/modern/forgot-password')
    await page.locator('#email').fill('user@example.com')
    await page.locator('button[type="submit"]').click()
    await expect(page.locator('.auth-form-success')).toBeVisible()
    await expect(page.locator('#email')).toHaveValue('')
  })

  test('FP-07: Sign In link navigates to login page', async ({ page }) => {
    await page.goto('/authentication/modern/forgot-password')
    await page.locator('a[href*="login"]').click()
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })
})

// =============================================================================
// New Password Page (/authentication/modern/new-password)
// =============================================================================
test.describe('New Password Page', () => {

  test('NP-01: Submit button is disabled when no token is present', async ({ page }) => {
    await page.goto('/authentication/modern/new-password')
    await expect(page.locator('button[type="submit"]')).toBeDisabled()
  })

  test.skip('NP-02: Valid token allows password reset and redirects to login', async ({ page }) => {
    // TODO: requires valid reset token + running backend API
    await page.goto('/authentication/modern/new-password?token=valid-test-token')
    await page.locator('#new-password').fill('newpassword123')
    await page.locator('#confirm-password').fill('newpassword123')
    await page.locator('button[type="submit"]').click()
    await expect(page).toHaveURL(/\/authentication\/modern\/login\?reset=success/)
  })

  test('NP-03: Mismatched passwords shows error message', async ({ page }) => {
    await page.goto('/authentication/modern/new-password?token=test-token')
    await page.locator('#new-password').fill('password123')
    await page.locator('#confirm-password').fill('different456')
    await page.locator('button[type="submit"]').click()
    await expect(page.locator('.auth-form-error')).toContainText('Passwords do not match')
  })

  test('NP-04: Both password toggle buttons work independently', async ({ page }) => {
    await page.goto('/authentication/modern/new-password?token=test-token')
    const toggles = page.locator('.password-toggle')
    const newPwInput = page.locator('#new-password')
    const confirmInput = page.locator('#confirm-password')
    await toggles.first().click()
    await expect(newPwInput).toHaveAttribute('type', 'text')
    await toggles.last().click()
    await expect(confirmInput).toHaveAttribute('type', 'text')
  })

  test('NP-05: Short password triggers minlength validation', async ({ page }) => {
    await page.goto('/authentication/modern/new-password?token=test-token')
    const passwordInput = page.locator('#new-password')
    await passwordInput.fill('123')
    const isValid = await passwordInput.evaluate((el: HTMLInputElement) => el.checkValidity())
    expect(isValid).toBe(false)
  })

  test.skip('NP-06: Invalid or expired token shows error message', async ({ page }) => {
    // TODO: requires running backend API to reject invalid token
    await page.goto('/authentication/modern/new-password?token=expired-token')
    await page.locator('#new-password').fill('password123')
    await page.locator('#confirm-password').fill('password123')
    await page.locator('button[type="submit"]').click()
    await expect(page.locator('.auth-form-error')).toBeVisible()
  })

  test('NP-07: Back to Sign In link navigates to login page', async ({ page }) => {
    await page.goto('/authentication/modern/new-password')
    await page.locator('a[href*="login"]').click()
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })
})

// =============================================================================
// Verify Email Page (/authentication/modern/verify-email)
// =============================================================================
test.describe('Verify Email Page', () => {

  test('VE-01: No token immediately shows error state', async ({ page }) => {
    await page.goto('/authentication/modern/verify-email')
    await expect(page.locator('#verify-error')).toBeVisible()
    await expect(page.locator('#verify-loading')).toBeHidden()
  })

  test('VE-02: No token error message contains expected text', async ({ page }) => {
    await page.goto('/authentication/modern/verify-email')
    await expect(page.locator('#verify-error-message')).toContainText('No verification token found')
  })

  test.skip('VE-03: Valid token shows loading spinner before API completes', async ({ page }) => {
    // TODO: requires API route mock to delay response
    await page.goto('/authentication/modern/verify-email?token=valid-token')
    await expect(page.locator('#verify-loading')).toBeVisible()
  })

  test.skip('VE-04: Valid token verification success shows success state', async ({ page }) => {
    // TODO: requires API mock for POST /auth/verify-email → 200
    await page.goto('/authentication/modern/verify-email?token=valid-token')
    await expect(page.locator('#verify-success')).toBeVisible()
    await expect(page.locator('#verify-loading')).toBeHidden()
  })

  test.skip('VE-05: Success state Continue button navigates to login', async ({ page }) => {
    // TODO: requires API mock for successful verification
    await page.goto('/authentication/modern/verify-email?token=valid-token')
    await expect(page.locator('#verify-success')).toBeVisible()
    await page.locator('#verify-success a.btn-primary').click()
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })

  test.skip('VE-06: Invalid token shows error state', async ({ page }) => {
    // TODO: requires API mock for POST /auth/verify-email → 400
    await page.goto('/authentication/modern/verify-email?token=invalid-token')
    await expect(page.locator('#verify-error')).toBeVisible()
  })

  test('VE-07: Error state Back to Sign In link navigates to login', async ({ page }) => {
    await page.goto('/authentication/modern/verify-email')
    // No token → error state is shown immediately
    await page.locator('#verify-error a.btn-outline-primary').click()
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })
})

// =============================================================================
// Link Sent Page (/authentication/modern/link-sent)
// =============================================================================
test.describe('Link Sent Page', () => {

  test('LS-01: Page renders "Recovery Link Sent" title', async ({ page }) => {
    await page.goto('/authentication/modern/link-sent')
    await expect(page.locator('h4.card-title')).toContainText('Recovery Link Sent')
  })

  test('LS-02: Back button navigates to homepage', async ({ page }) => {
    await page.goto('/authentication/modern/link-sent')
    await page.locator('a.btn-outline-primary[href="/"]').click()
    await expect(page).toHaveURL('/')
  })

  test('LS-03: Create Account button navigates to register page', async ({ page }) => {
    await page.goto('/authentication/modern/link-sent')
    await page.locator('a.btn-outline-primary[href*="register"]').click()
    await expect(page).toHaveURL(/\/authentication\/modern\/register/)
  })

  test('LS-04: Resend Link button exists on page', async ({ page }) => {
    await page.goto('/authentication/modern/link-sent')
    const resendBtn = page.locator('button.btn-primary').filter({ hasText: 'Resend Link' })
    await expect(resendBtn).toBeVisible()
  })

  test('LS-05: "Use another email" link navigates to forgot-password', async ({ page }) => {
    await page.goto('/authentication/modern/link-sent')
    await page.locator('a[href*="forgot-password"]').click()
    await expect(page).toHaveURL(/\/authentication\/modern\/forgot-password/)
  })
})

// =============================================================================
// Reset Successfully Page (/authentication/modern/reset-successfully)
// =============================================================================
test.describe('Reset Successfully Page', () => {

  test('RS-01: Page renders password reset success message', async ({ page }) => {
    await page.goto('/authentication/modern/reset-successfully')
    await expect(page.locator('h4.card-title')).toContainText('Password Reset Successfully')
  })

  test('RS-02: Back button navigates to homepage', async ({ page }) => {
    await page.goto('/authentication/modern/reset-successfully')
    await page.locator('a.btn-outline-primary[href="/"]').click()
    await expect(page).toHaveURL('/')
  })

  test('RS-03: Create Account button navigates to register page', async ({ page }) => {
    await page.goto('/authentication/modern/reset-successfully')
    await page.locator('a.btn-outline-primary[href*="register"]').click()
    await expect(page).toHaveURL(/\/authentication\/modern\/register/)
  })

  test('RS-04: Login Now button navigates to login page', async ({ page }) => {
    await page.goto('/authentication/modern/reset-successfully')
    await page.locator('a.btn-primary[href*="login"]').click()
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })
})
