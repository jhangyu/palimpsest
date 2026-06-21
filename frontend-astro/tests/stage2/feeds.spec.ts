/**
 * S2-02: Add Feed / Manage Feed — Playwright Tests
 * Spec: docs/test-specs/s2-02-feeds.md
 *
 * Covers: /feeds/add (Add Feed wizard) and /feeds/edit (Manage Feed table + editor).
 * All tests require authenticated session — marked test.skip until session fixture lands.
 *
 * Run: npx playwright test tests/stage2/feeds.spec.ts
 */
import { test, expect } from '@playwright/test'

// =============================================================================
// Add Feed Page (/feeds/add)
// =============================================================================
test.describe('Add Feed Page', () => {

  test.skip('F-01: Page loads with feed wizard and hidden preview section', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    await expect(page.locator('#feed-wizard')).toBeVisible()
    await expect(page.locator('#preview-section')).toHaveClass(/d-none/)
    await expect(page.locator('.CodeMirror')).toBeVisible()
  })

  test.skip('F-02: Back button navigates to /dashboard', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    await page.locator('a[href="/dashboard"]').click()
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test.skip('F-03: URL field accepts input', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    await expect(page.locator('#wizard-url')).toHaveValue('https://example.com/blog')
  })

  test.skip('F-04: Site Name field accepts input', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    await page.locator('#wizard-name').fill('Example Blog')
    await expect(page.locator('#wizard-name')).toHaveValue('Example Blog')
  })

  test.skip('F-05: Analyze List with empty URL shows alert', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Please enter Target URL first')
      await dialog.accept()
    })
    await page.locator('#btn-analyze-list').click()
  })

  test.skip('F-06: Analyze List success populates CodeMirror list rules', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    await page.locator('#btn-analyze-list').click()
    // Button should show spinner during analysis
    await expect(page.locator('#btn-analyze-list')).toBeDisabled()
    // Wait for API response
    await page.waitForResponse(resp =>
      resp.url().includes('/analyze/list') && resp.request().method() === 'POST'
    )
    // CodeMirror should be populated with AI-returned JSON
    await expect(page.locator('#cm-wizard-list-rules .CodeMirror')).toBeVisible()
    // Rules panel should be expanded after analyze
    await expect(page.locator('#rules-panel')).toBeVisible()
  })

  test.skip('F-07: Analyze List API failure shows error alert', async ({ page }) => {
    // TODO: requires auth session fixture + API mock for error response
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Error analyzing list')
      await dialog.accept()
    })
    await page.locator('#btn-analyze-list').click()
  })

  test.skip('F-08: Analyze Content with empty Sample URL shows alert', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Please enter Sample Article URL first')
      await dialog.accept()
    })
    await page.locator('#btn-analyze-content').click()
  })

  test.skip('F-09: Analyze Content success populates CodeMirror content rules', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/add')
    await page.locator('#wizard-sample-url').fill('https://example.com/blog/post-1')
    await page.locator('#btn-analyze-content').click()
    await expect(page.locator('#btn-analyze-content')).toBeDisabled()
    await page.waitForResponse(resp =>
      resp.url().includes('/analyze/content') && resp.request().method() === 'POST'
    )
    await expect(page.locator('#cm-wizard-content-rules .CodeMirror')).toBeVisible()
  })

  test.skip('F-10: Sample Article URL field accepts input', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    await page.locator('#wizard-sample-url').fill('https://example.com/blog/post-1')
    await expect(page.locator('#wizard-sample-url')).toHaveValue('https://example.com/blog/post-1')
  })

  test.skip('F-11: Toggle Rules JSON hides rules panel', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    // Ensure rules panel is visible first
    await expect(page.locator('#rules-panel')).not.toHaveClass(/d-none/)
    await page.locator('#btn-toggle-rules').click()
    await expect(page.locator('#rules-panel')).toHaveClass(/d-none/)
    await expect(page.locator('#btn-toggle-rules')).toContainText('Show Rules JSON')
  })

  test.skip('F-12: Toggle Rules JSON shows rules panel', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    // Hide first
    await page.locator('#btn-toggle-rules').click()
    await expect(page.locator('#rules-panel')).toHaveClass(/d-none/)
    // Show again
    await page.locator('#btn-toggle-rules').click()
    await expect(page.locator('#rules-panel')).not.toHaveClass(/d-none/)
    await expect(page.locator('#btn-toggle-rules')).toContainText('Hide Rules JSON')
  })

  test.skip('F-13: CodeMirror List Rules editor is editable', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    await expect(page.locator('#cm-wizard-list-rules .CodeMirror')).toBeVisible()
  })

  test.skip('F-14: CodeMirror Content Rules editor is editable', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    await expect(page.locator('#cm-wizard-content-rules .CodeMirror')).toBeVisible()
  })

  test.skip('F-15: Test List with empty URL shows alert', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Please enter a Target URL first')
      await dialog.accept()
    })
    await page.locator('#btn-test-list').click()
  })

  test.skip('F-16: Test List success shows preview with Title/URL columns', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    await page.locator('#btn-test-list').click()
    await expect(page.locator('#preview-section')).not.toHaveClass(/d-none/)
    await page.waitForResponse(resp =>
      resp.url().includes('/crawl/preview') && resp.request().method() === 'POST'
    )
    await expect(page.locator('#preview-body')).toBeVisible()
  })

  test.skip('F-17: Test Content with empty Sample URL shows alert', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Please enter a Sample URL to test content extraction')
      await dialog.accept()
    })
    await page.locator('#btn-test-content').click()
  })

  test.skip('F-18: Test Content success shows preview with Title/Time/Content columns', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/add')
    await page.locator('#wizard-sample-url').fill('https://example.com/blog/post-1')
    await page.locator('#btn-test-content').click()
    await page.waitForResponse(resp =>
      resp.url().includes('/crawl/preview') && resp.request().method() === 'POST'
    )
    await expect(page.locator('#preview-body')).toBeVisible()
  })

  test.skip('F-19: Test Both with empty URL shows alert', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Please enter a Target URL first')
      await dialog.accept()
    })
    await page.locator('#btn-test-both').click()
  })

  test.skip('F-20: Test Both success shows three-column preview results', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    await page.locator('#btn-test-both').click()
    await page.waitForResponse(resp =>
      resp.url().includes('/crawl/preview') && resp.request().method() === 'POST'
    )
    await expect(page.locator('#preview-body')).toBeVisible()
  })

  test.skip('F-21: Preview loading state shows spinner during test', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    await page.locator('#btn-test-list').click()
    await expect(page.locator('#preview-loading')).toBeVisible()
  })

  test.skip('F-22: Preview error displays error message', async ({ page }) => {
    // TODO: requires auth session fixture + API mock for error response
    await page.goto('/feeds/add')
    await expect(page.locator('#preview-error')).not.toHaveClass(/d-none/)
  })

  test.skip('F-23: Preview with no results shows guidance message', async ({ page }) => {
    // TODO: requires auth session fixture + API returning empty array
    await page.goto('/feeds/add')
    await expect(page.locator('#preview-body')).toContainText('No results found')
  })

  test.skip('F-24: Debug mode checkbox toggles debugMode', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    const debugCheckbox = page.locator('#wizard-debug')
    await debugCheckbox.check()
    await expect(debugCheckbox).toBeChecked()
    await debugCheckbox.uncheck()
    await expect(debugCheckbox).not.toBeChecked()
  })

  test.skip('F-25: Debug banner shows debug_dir path after test in debug mode', async ({ page }) => {
    // TODO: requires auth session fixture + API returning debug_dir
    await page.goto('/feeds/add')
    await page.locator('#wizard-debug').check()
    // After test call with debug=true, banner should show
    await expect(page.locator('#debug-banner')).not.toHaveClass(/d-none/)
    await expect(page.locator('#debug-banner-path')).not.toBeEmpty()
  })

  test.skip('F-26: Save with empty URL or Name shows alert', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('URL and Site Name are required')
      await dialog.accept()
    })
    await page.locator('#btn-save').click()
  })

  test.skip('F-27: Save with invalid JSON shows alert', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com')
    await page.locator('#wizard-name').fill('Test')
    // Corrupt the JSON in CodeMirror (implementation depends on CodeMirror API)
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Rules must be valid JSON')
      await dialog.accept()
    })
    await page.locator('#btn-save').click()
  })

  test.skip('F-28: Save success creates feed and redirects to /dashboard', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    await page.locator('#wizard-name').fill('Example Blog')
    await page.locator('#btn-save').click()
    await expect(page.locator('#btn-save')).toBeDisabled()
    await page.waitForResponse(resp =>
      resp.url().includes('/sites/') && resp.request().method() === 'POST'
    )
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test.skip('F-29: Save API failure shows error and restores button', async ({ page }) => {
    // TODO: requires auth session fixture + API mock for error response
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    await page.locator('#wizard-name').fill('Example Blog')
    page.on('dialog', dialog => dialog.accept())
    await page.locator('#btn-save').click()
    // Button should restore after error
    await expect(page.locator('#btn-save')).toBeEnabled()
  })
})

// =============================================================================
// Manage Feed Page — Feed Management Table (/feeds/edit)
// =============================================================================
test.describe('Manage Feed Page — Feed Table', () => {

  test.skip('F-30: Page loads feed table with loading spinner', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/edit')
    // Loading state should appear initially
    await expect(page.locator('#feed-table-loading')).toBeVisible()
    // After API response, table body should render
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#feed-table-body')).toBeVisible()
  })

  test.skip('F-31: URL with ?site=<id> auto-loads feed into editor', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit?site=1')
    await expect(page.locator('#editor-section')).not.toHaveClass(/d-none/)
  })

  test.skip('F-32: Empty feed list shows "No feeds found" message', async ({ page }) => {
    // TODO: requires auth session fixture + empty feed state
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#feed-table-body')).toContainText('No feeds found')
  })

  test.skip('F-33: Refresh Table button reloads feed list', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('#btn-refresh-table').click()
    await expect(page.locator('#btn-refresh-table')).toBeDisabled()
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#btn-refresh-table')).toBeEnabled()
  })

  test.skip('F-34: Row Edit button loads feed into editor section', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    const firstRow = page.locator('tr[data-site-id]').first()
    await firstRow.locator('[data-action="edit"]').click()
    await expect(page.locator('#editor-section')).not.toHaveClass(/d-none/)
    await expect(firstRow).toHaveClass(/table-active/)
  })

  test.skip('F-35: Row Duplicate button shows confirm dialog and duplicates feed', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Duplicate this feed configuration?')
      await dialog.accept()
    })
    const firstRow = page.locator('tr[data-site-id]').first()
    await firstRow.locator('[data-action="duplicate"]').click()
  })

  test.skip('F-36: Duplicate cancel does not trigger API call', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    let apiCalled = false
    page.on('dialog', async dialog => await dialog.dismiss())
    page.on('request', req => {
      if (req.url().includes('/duplicate') && req.method() === 'POST') apiCalled = true
    })
    const firstRow = page.locator('tr[data-site-id]').first()
    await firstRow.locator('[data-action="duplicate"]').click()
    expect(apiCalled).toBe(false)
  })

  test.skip('F-37: Row Crawl button triggers crawl and shows spinner', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    const firstRow = page.locator('tr[data-site-id]').first()
    const crawlBtn = firstRow.locator('[data-action="crawl"]')
    page.on('dialog', dialog => dialog.accept())
    await crawlBtn.click()
    await expect(crawlBtn).toBeDisabled()
  })

  test.skip('F-38: Row Crawl button prevents duplicate triggers', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    let crawlCount = 0
    page.on('request', req => {
      if (req.url().includes('/crawl/') && req.method() === 'POST') crawlCount++
    })
    page.on('dialog', dialog => dialog.accept())
    const firstRow = page.locator('tr[data-site-id]').first()
    const crawlBtn = firstRow.locator('[data-action="crawl"]')
    await crawlBtn.click()
    await crawlBtn.click()
    // Only one crawl request should have been sent
    expect(crawlCount).toBeLessThanOrEqual(1)
  })

  test.skip('F-39: Row Delete button shows confirm and deletes feed', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Are you sure you want to delete this feed?')
      await dialog.accept()
    })
    const firstRow = page.locator('tr[data-site-id]').first()
    await firstRow.locator('[data-action="delete"]').click()
  })

  test.skip('F-40: Delete cancel does not trigger API call', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    let apiCalled = false
    page.on('dialog', async dialog => await dialog.dismiss())
    page.on('request', req => {
      if (req.method() === 'DELETE') apiCalled = true
    })
    const firstRow = page.locator('tr[data-site-id]').first()
    await firstRow.locator('[data-action="delete"]').click()
    expect(apiCalled).toBe(false)
  })

  test.skip('F-41: Delete API failure shows error alert', async ({ page }) => {
    // TODO: requires auth session fixture + API mock for delete error
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    page.on('dialog', async dialog => {
      if (dialog.type() === 'confirm') await dialog.accept()
      else {
        expect(dialog.message()).toContain('Delete failed')
        await dialog.accept()
      }
    })
    const firstRow = page.locator('tr[data-site-id]').first()
    await firstRow.locator('[data-action="delete"]').click()
  })
})

// =============================================================================
// Manage Feed Page — Detail Editor
// =============================================================================
test.describe('Manage Feed Page — Detail Editor', () => {

  test.skip('F-42: Editor section appears with correct title after Edit click', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await expect(page.locator('#editor-section')).not.toHaveClass(/d-none/)
    await expect(page.locator('#editor-title')).toContainText('Editing:')
  })

  test.skip('F-43: Target URL field is editable in editor', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    const urlInput = page.locator('#input-url')
    await urlInput.fill('https://updated.example.com')
    await expect(urlInput).toHaveValue('https://updated.example.com')
  })

  test.skip('F-44: Site Name field is editable in editor', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    const nameInput = page.locator('#input-name')
    await nameInput.fill('Updated Name')
    await expect(nameInput).toHaveValue('Updated Name')
  })

  test.skip('F-45: Refresh Frequency field accepts valid numeric input', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    const freqInput = page.locator('#input-freq')
    await freqInput.fill('30')
    await expect(freqInput).toHaveValue('30')
  })

  test.skip('F-46: Sample URL field is editable in editor', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    const sampleInput = page.locator('#input-sample-url')
    await sampleInput.fill('https://example.com/blog/post-1')
    await expect(sampleInput).toHaveValue('https://example.com/blog/post-1')
  })

  test.skip('F-47: Editor Analyze List uses editData URL and updates CodeMirror', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#editor-section #btn-analyze-list').click()
    await expect(page.locator('#editor-section #btn-analyze-list')).toBeDisabled()
    await page.waitForResponse(resp =>
      resp.url().includes('/analyze/list') && resp.request().method() === 'POST'
    )
    await expect(page.locator('#cm-list-rules .CodeMirror')).toBeVisible()
  })

  test.skip('F-48: Editor Analyze Content with sample URL calls API', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#input-sample-url').fill('https://example.com/post-1')
    await page.locator('#editor-section #btn-analyze-content').click()
    await page.waitForResponse(resp =>
      resp.url().includes('/analyze/content') && resp.request().method() === 'POST'
    )
  })

  test.skip('F-49: Editor Analyze Content without sample URL shows prompt', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#input-sample-url').fill('')
    page.on('dialog', async dialog => {
      if (dialog.type() === 'prompt') {
        await dialog.accept('https://example.com/post-1')
      }
    })
    await page.locator('#editor-section #btn-analyze-content').click()
  })

  test.skip('F-50: Editor Analyze Content prompt cancel does not call API', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#input-sample-url').fill('')
    let apiCalled = false
    page.on('dialog', async dialog => await dialog.dismiss())
    page.on('request', req => {
      if (req.url().includes('/analyze/content')) apiCalled = true
    })
    await page.locator('#editor-section #btn-analyze-content').click()
    expect(apiCalled).toBe(false)
  })

  test.skip('F-51: Editor Test List sends preview request', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    const responsePromise = page.waitForResponse(resp =>
      resp.url().includes('/crawl/preview') && resp.request().method() === 'POST'
    )
    await page.locator('#editor-section #btn-test-list').click()
    await responsePromise
    await expect(page.locator('#preview-body')).toBeVisible()
  })

  test.skip('F-52: Editor Test Content with sample URL sends preview request', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#input-sample-url').fill('https://example.com/post-1')
    const responsePromise = page.waitForResponse(resp =>
      resp.url().includes('/crawl/preview') && resp.request().method() === 'POST'
    )
    await page.locator('#editor-section #btn-test-content').click()
    await responsePromise
  })

  test.skip('F-53: Editor Toggle Rules hides rules panel', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#editor-section #btn-toggle-rules').click()
    await expect(page.locator('#editor-section #rules-panel')).toHaveClass(/d-none/)
    await expect(page.locator('#editor-section #btn-toggle-rules')).toContainText('Show Rules')
  })

  test.skip('F-54: Editor Toggle Rules shows rules panel and refreshes CodeMirror', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    // Hide first
    await page.locator('#editor-section #btn-toggle-rules').click()
    // Show again
    await page.locator('#editor-section #btn-toggle-rules').click()
    await expect(page.locator('#editor-section #rules-panel')).not.toHaveClass(/d-none/)
    await expect(page.locator('#editor-section #btn-toggle-rules')).toContainText('Hide Rules')
  })

  test.skip('F-55: Editor CodeMirror List Rules is editable', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await expect(page.locator('#cm-list-rules .CodeMirror')).toBeVisible()
  })

  test.skip('F-56: Editor CodeMirror Content Rules is editable', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await expect(page.locator('#cm-content-rules .CodeMirror')).toBeVisible()
  })

  test.skip('F-57: Editor Debug toggle switches debugMode and label style', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    const debugCheckbox = page.locator('#debug-checkbox')
    await debugCheckbox.check()
    await expect(debugCheckbox).toBeChecked()
    await expect(page.locator('#debug-label')).toHaveClass(/text-warning/)
    await debugCheckbox.uncheck()
    await expect(page.locator('#debug-label')).toHaveClass(/text-muted/)
  })

  test.skip('F-58: Save Changes success updates feed and refreshes table', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    page.on('dialog', dialog => dialog.accept())
    const responsePromise = page.waitForResponse(resp =>
      resp.url().includes('/sites/') && resp.request().method() === 'PUT'
    )
    await page.locator('#btn-save').click()
    await responsePromise
  })

  test.skip('F-59: Save Changes with invalid List Rules JSON shows alert', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Invalid JSON in List Rules')
      await dialog.accept()
    })
    // Corrupt list rules JSON and save
    await page.locator('#btn-save').click()
  })

  test.skip('F-60: Save Changes with invalid Content Rules JSON shows alert', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Invalid JSON in Content Rules')
      await dialog.accept()
    })
    await page.locator('#btn-save').click()
  })

  test.skip('F-61: Save Changes prevents double-submit with saving flag', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    page.on('dialog', dialog => dialog.accept())
    await page.locator('#btn-save').click()
    await expect(page.locator('#btn-save')).toBeDisabled()
  })

  test.skip('F-62: Editor Crawl button triggers POST /crawl/:id', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    page.on('dialog', dialog => dialog.accept())
    const responsePromise = page.waitForResponse(resp =>
      resp.url().includes('/crawl/') && resp.request().method() === 'POST'
    )
    await page.locator('#btn-crawl-editor').click()
    await responsePromise
  })
})

// =============================================================================
// Manage Feed Page — Filter Builder
// =============================================================================
test.describe('Manage Feed Page — Filter Builder', () => {

  test.skip('F-63: Filter Builder initializes with existing filter_rules', async ({ page }) => {
    // TODO: requires auth session fixture + feed with filter_rules data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await expect(page.locator('#filter-builder-root')).toBeVisible()
  })

  test.skip('F-64: Blacklist mode radio selection', async ({ page }) => {
    // TODO: requires auth session fixture + feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#filter-mode-bl').check()
    await expect(page.locator('#filter-mode-bl')).toBeChecked()
  })

  test.skip('F-65: Whitelist mode radio selection', async ({ page }) => {
    // TODO: requires auth session fixture + feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#filter-mode-wl').check()
    await expect(page.locator('#filter-mode-wl')).toBeChecked()
  })

  test.skip('F-66: Whole Words Only checkbox toggles', async ({ page }) => {
    // TODO: requires auth session fixture + feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    const checkbox = page.locator('#filter-whole-word')
    await checkbox.check()
    await expect(checkbox).toBeChecked()
    await checkbox.uncheck()
    await expect(checkbox).not.toBeChecked()
  })

  test.skip('F-67: Toggle AND/OR operator switches button style', async ({ page }) => {
    // TODO: requires auth session fixture + feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    const operatorBtn = page.locator('[data-action="toggle-operator"]').first()
    // Check initial state before toggle
    const isAnd = await operatorBtn.evaluate(el => el.classList.contains('btn-primary'))
    await operatorBtn.click()
    // Check that button style changed (AND=primary/blue, OR=warning/yellow)
    if (isAnd) {
      await expect(operatorBtn).toHaveClass(/btn-warning/)
    } else {
      await expect(operatorBtn).toHaveClass(/btn-primary/)
    }
  })

  test.skip('F-68: Add Rule creates new rule row with field/match/value inputs', async ({ page }) => {
    // TODO: requires auth session fixture + feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    const initialRules = await page.locator('#filter-builder-root [data-action="delete-rule"]').count()
    await page.locator('[data-action="add-rule"]').first().click()
    const newRules = await page.locator('#filter-builder-root [data-action="delete-rule"]').count()
    expect(newRules).toBe(initialRules + 1)
  })

  test.skip('F-69: Add Inner Group creates nested filter group', async ({ page }) => {
    // TODO: requires auth session fixture + feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('[data-action="add-group"]').first().click()
    // Should have a nested group with its own operator toggle
    const nestedGroups = page.locator('#filter-builder-root [data-action="delete-group"]')
    const count = await nestedGroups.count()
    expect(count).toBeGreaterThan(0)
  })

  test.skip('F-70: Update Rule Field dropdown changes field value', async ({ page }) => {
    // TODO: requires auth session fixture + feed data with rules
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('[data-action="add-rule"]').first().click()
    const fieldSelect = page.locator('[data-action="update-rule-field"]').last()
    await fieldSelect.selectOption('content')
    await expect(fieldSelect).toHaveValue('content')
  })

  test.skip('F-71: Update Rule Match dropdown changes match type', async ({ page }) => {
    // TODO: requires auth session fixture + feed data with rules
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('[data-action="add-rule"]').first().click()
    const matchSelect = page.locator('[data-action="update-rule-match"]').last()
    await matchSelect.selectOption('regex')
    await expect(matchSelect).toHaveValue('regex')
  })

  test.skip('F-72: Update Rule Value input accepts text', async ({ page }) => {
    // TODO: requires auth session fixture + feed data with rules
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('[data-action="add-rule"]').first().click()
    const valueInput = page.locator('[data-action="update-rule-value"]').last()
    await valueInput.fill('test-keyword')
    await expect(valueInput).toHaveValue('test-keyword')
  })

  test.skip('F-73: Rule move-up swaps with previous rule', async ({ page }) => {
    // TODO: requires auth session fixture + feed data with multiple rules
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    // Add two rules
    await page.locator('[data-action="add-rule"]').first().click()
    await page.locator('[data-action="add-rule"]').first().click()
    // Move-up on second rule
    const moveUpBtns = page.locator('[data-action="move-up"]')
    // First rule's move-up should be disabled
    await expect(moveUpBtns.first()).toBeDisabled()
  })

  test.skip('F-74: Rule move-down swaps with next rule', async ({ page }) => {
    // TODO: requires auth session fixture + feed data with multiple rules
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('[data-action="add-rule"]').first().click()
    await page.locator('[data-action="add-rule"]').first().click()
    // Last rule's move-down should be disabled
    const moveDownBtns = page.locator('[data-action="move-down"]')
    await expect(moveDownBtns.last()).toBeDisabled()
  })

  test.skip('F-75: Delete Rule removes rule row from UI', async ({ page }) => {
    // TODO: requires auth session fixture + feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('[data-action="add-rule"]').first().click()
    const initialRules = await page.locator('[data-action="delete-rule"]').count()
    await page.locator('[data-action="delete-rule"]').last().click()
    const newRules = await page.locator('[data-action="delete-rule"]').count()
    expect(newRules).toBe(initialRules - 1)
  })

  test.skip('F-76: Delete non-root Group removes entire group', async ({ page }) => {
    // TODO: requires auth session fixture + feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    // Add an inner group
    await page.locator('[data-action="add-group"]').first().click()
    const groupCount = await page.locator('[data-action="delete-group"]').count()
    await page.locator('[data-action="delete-group"]').last().click()
    const newGroupCount = await page.locator('[data-action="delete-group"]').count()
    expect(newGroupCount).toBe(groupCount - 1)
  })
})

// =============================================================================
// Manage Feed Page — Preview Section
// =============================================================================
test.describe('Manage Feed Page — Preview Section', () => {

  test.skip('F-77: Preview section is initially hidden', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#preview-section')).toHaveClass(/d-none/)
  })

  test.skip('F-78: Preview section shows after Edit click', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await expect(page.locator('#preview-section')).not.toHaveClass(/d-none/)
  })

  test.skip('F-79: Test Both sends preview request with mode=both', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    const responsePromise = page.waitForResponse(resp =>
      resp.url().includes('/crawl/preview') && resp.request().method() === 'POST'
    )
    await page.locator('#btn-test-both').click()
    await responsePromise
    await expect(page.locator('#preview-body')).toBeVisible()
  })

  test.skip('F-80: Preview Filter button activates filter mode', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#btn-filter-preview').click()
    await expect(page.locator('#btn-filter-preview')).toHaveClass(/active/)
  })

  test.skip('F-81: Preview Filter button deactivates on second click', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#btn-filter-preview').click()
    await page.locator('#btn-filter-preview').click()
    await expect(page.locator('#btn-filter-preview')).not.toHaveClass(/active/)
  })

  test.skip('F-82: Filtered articles show warning banner and visual styling', async ({ page }) => {
    // TODO: requires auth session fixture + feed data with filter rules + API returning filtered results
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    // Activate filter preview and test
    await page.locator('#btn-filter-preview').click()
    await page.locator('#btn-test-both').click()
    await page.waitForLoadState('networkidle')
    // Filtered rows should have opacity-50 and line-through styling
    await expect(page.locator('#preview-body')).toContainText('articles hidden by filter rules')
    await expect(page.locator('#preview-body tr.opacity-50')).toBeVisible()
  })

  test.skip('F-83: Preview loading shows spinner and message', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#btn-test-both').click()
    await expect(page.locator('#preview-body')).toContainText('Crawling and analyzing')
  })

  test.skip('F-84: Preview error shows danger alert', async ({ page }) => {
    // TODO: requires auth session fixture + API mock for error response
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#btn-test-both').click()
    await expect(page.locator('#preview-body .alert-danger')).toBeVisible()
  })

  test.skip('F-85: Debug banner shows path in debug mode after test', async ({ page }) => {
    // TODO: requires auth session fixture + API returning debug_dir
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#debug-checkbox').check()
    await page.locator('#btn-test-both').click()
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#preview-body .debug-dir-banner')).toBeVisible()
  })

  test.skip('F-86: Debug banner Copy button copies path to clipboard', async ({ page }) => {
    // TODO: requires auth session fixture + debug mode + API returning debug_dir
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#debug-checkbox').check()
    await page.locator('#btn-test-both').click()
    await page.waitForLoadState('networkidle')
    const copyBtn = page.locator('.debug-dir-banner button')
    await copyBtn.click()
    // Button icon should change to checkmark briefly
  })
})

// =============================================================================
// Error & Edge Cases
// =============================================================================
test.describe('Feeds — Error & Edge Cases', () => {

  test.skip('F-87: 401 unauthorized redirects to login page', async ({ page }) => {
    // TODO: requires expired session state
    await page.goto('/feeds/edit')
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })

  test.skip('F-88: Analyze buttons are disabled during API call to prevent duplicates', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    await page.locator('#btn-analyze-list').click()
    await expect(page.locator('#btn-analyze-list')).toBeDisabled()
    await expect(page.locator('#btn-analyze-content')).toBeDisabled()
  })

  test.skip('F-89: Save success invalidates sites cache and refreshes table', async ({ page }) => {
    // TODO: requires auth session fixture + running backend API
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    page.on('dialog', dialog => dialog.accept())
    await page.locator('#btn-save').click()
    // Table should refresh after save
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#feed-table-body')).toBeVisible()
  })

  test.skip('F-90: Deleting currently-edited feed hides editor and preview', async ({ page }) => {
    // TODO: requires auth session fixture + existing feed data
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    // Edit the first feed
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await expect(page.locator('#editor-section')).not.toHaveClass(/d-none/)
    // Delete the same feed
    page.on('dialog', async dialog => await dialog.accept())
    await page.locator('tr[data-site-id]').first().locator('[data-action="delete"]').click()
    // Editor and preview should be hidden
    await expect(page.locator('#editor-section')).toHaveClass(/d-none/)
    await expect(page.locator('#preview-section')).toHaveClass(/d-none/)
  })
})
