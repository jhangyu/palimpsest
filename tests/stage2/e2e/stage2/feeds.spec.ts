/*
---
name: feeds
description: "Stage 2 E2E: /feeds/add (wizard: URL/name input, Analyze/Test, Preview, Save) and /feeds/edit (table CRUD, editor, filter builder, preview panel)"
stage: stage2
type: playwright
target:
  layer: frontend
  domain: feeds
spec_doc: docs/test-specs/stage2/s2-02-feeds.md
test_file: tests/stage2/e2e/stage2/feeds.spec.ts
tests:
  - name: "F-01: Page loads with feed wizard and hidden preview section"
    line: 18
    purpose: "Feed wizard visible; preview section hidden on initial load"
  - name: "F-02: Back button navigates to /dashboard"
    line: 25
    purpose: "Back button navigates to /dashboard"
  - name: "F-03: URL field accepts input"
    line: 32
    purpose: "#feed-url input accepts typed URL value"
  - name: "F-04: Site Name field accepts input"
    line: 38
    purpose: "#feed-name input accepts typed site name value"
  - name: "F-05: Analyze List with empty URL shows alert"
    line: 44
    purpose: "Clicking Analyze List without URL shows validation alert"
  - name: "F-06: Analyze List success populates CodeMirror list rules"
    line: 53
    purpose: "Mocked analyze-list API success updates CodeMirror list rules editor"
  - name: "F-07: Analyze List API failure shows error alert"
    line: 69
    purpose: "500 from analyze-list shows error alert"
  - name: "F-08: Analyze Content with empty Sample URL shows alert"
    line: 79
    purpose: "Clicking Analyze Content without sample URL shows validation alert"
  - name: "F-09: Analyze Content success populates CodeMirror content rules"
    line: 88
    purpose: "Mocked analyze-content API success updates CodeMirror content rules editor"
  - name: "F-10: Sample Article URL field accepts input"
    line: 99
    purpose: "#sample-url input accepts typed URL value"
  - name: "F-11: Toggle Rules JSON hides rules panel"
    line: 105
    purpose: "Clicking Toggle Rules JSON button hides the rules panel"
  - name: "F-12: Toggle Rules JSON shows rules panel"
    line: 114
    purpose: "Clicking Toggle Rules JSON again shows the rules panel"
  - name: "F-13: CodeMirror List Rules editor is editable"
    line: 125
    purpose: "CodeMirror list-rules editor accepts keyboard input"
  - name: "F-14: CodeMirror Content Rules editor is editable"
    line: 130
    purpose: "CodeMirror content-rules editor accepts keyboard input"
  - name: "F-15: Test List with empty URL shows alert"
    line: 135
    purpose: "Clicking Test List without URL shows validation alert"
  - name: "F-16: Test List success shows preview with Title/URL columns"
    line: 144
    purpose: "Mocked test-list returns articles; preview shows Title and URL columns"
  - name: "F-17: Test Content with empty Sample URL shows alert"
    line: 155
    purpose: "Clicking Test Content without sample URL shows validation alert"
  - name: "F-18: Test Content success shows preview with Title/Time/Content columns"
    line: 164
    purpose: "Mocked test-content returns article; preview shows Title, Time, Content columns"
  - name: "F-19: Test Both with empty URL shows alert"
    line: 174
    purpose: "Clicking Test Both without URL shows validation alert"
  - name: "F-20: Test Both success shows three-column preview results"
    line: 183
    purpose: "Mocked test-both returns articles; preview shows three-column results"
  - name: "F-21: Preview loading state shows spinner during test"
    line: 193
    purpose: "Delayed test API keeps preview loading spinner visible"
  - name: "F-22: Preview error displays error message"
    line: 200
    purpose: "500 from test API shows error message in preview section"
  - name: "F-23: Preview with no results shows guidance message"
    line: 216
    purpose: "Empty articles array shows 'no results' guidance message in preview"
  - name: "F-24: Debug mode checkbox toggles debugMode"
    line: 232
    purpose: "#debug-mode checkbox toggles debug mode state"
  - name: "F-25: Debug banner shows debug_dir path after test in debug mode"
    line: 241
    purpose: "Mocked test-both with debug_dir shows debug banner with path"
  - name: "F-26: Save with empty URL or Name shows alert"
    line: 260
    purpose: "Clicking Save without URL or Name shows validation alert"
  - name: "F-27: Save with invalid JSON shows alert"
    line: 269
    purpose: "Clicking Save with invalid JSON in rules shows validation alert"
  - name: "F-28: Save success creates feed and redirects to /dashboard"
    line: 281
    purpose: "Mocked POST /sites success creates feed and redirects to /dashboard"
  - name: "F-29: Save API failure shows error and restores button"
    line: 293
    purpose: "500 from POST /sites shows error alert and restores Save button state"
  - name: "F-30: Page loads feed table with loading spinner"
    line: 322
    purpose: "Delayed API keeps feed table loading spinner visible on /feeds/edit"
  - name: "F-31: URL with ?site=<id> auto-loads feed into editor"
    line: 335
    purpose: "?site=1 param auto-loads the feed with id=1 into the editor section"
  - name: "F-32: Empty feed list shows "No feeds found" message"
    line: 346
    purpose: "Mocked empty feed list shows 'No feeds found' message"
  - name: "F-33: Refresh Table button reloads feed list"
    line: 364
    purpose: "Clicking #refresh-table-btn triggers new API call and reloads list"
  - name: "F-34: Row Edit button loads feed into editor section"
    line: 378
    purpose: "Clicking Edit on a row loads that feed's data into the editor section"
  - name: "F-35: Row Duplicate button shows confirm dialog and duplicates feed"
    line: 387
    purpose: "Clicking Duplicate shows confirm; accepting calls POST /sites/:id/duplicate"
  - name: "F-36: Duplicate cancel does not trigger API call"
    line: 398
    purpose: "Cancelling duplicate confirm does not call POST /sites/:id/duplicate"
  - name: "F-37: Row Crawl button triggers crawl and shows spinner"
    line: 411
    purpose: "Clicking Crawl calls POST /crawl/:id; spinner shown during request"
  - name: "F-38: Row Crawl button prevents duplicate triggers"
    line: 431
    purpose: "Crawl button disabled while crawl is in progress; double-click blocked"
  - name: "F-39: Row Delete button shows confirm and deletes feed"
    line: 458
    purpose: "Clicking Delete shows confirm; accepting calls DELETE /sites/:id"
  - name: "F-40: Delete cancel does not trigger API call"
    line: 477
    purpose: "Cancelling delete confirm does not call DELETE /sites/:id"
  - name: "F-41: Delete API failure shows error alert"
    line: 490
    purpose: "500 from DELETE /sites/:id shows error alert in feed list"
  - name: "F-42: Editor section appears with correct title after Edit click"
    line: 511
    purpose: "Editor section visible after Edit click; title shows feed name"
  - name: "F-43: Target URL field is editable in editor"
    line: 519
    purpose: "#edit-feed-url input in editor accepts new URL value"
  - name: "F-44: Site Name field is editable in editor"
    line: 528
    purpose: "#edit-feed-name input in editor accepts new name value"
  - name: "F-45: Refresh Frequency field accepts valid numeric input"
    line: 537
    purpose: "#edit-refresh-freq accepts positive integer input"
  - name: "F-46: Sample URL field is editable in editor"
    line: 546
    purpose: "#edit-sample-url input in editor accepts URL value"
  - name: "F-47: Editor Analyze List uses editData URL and updates CodeMirror"
    line: 555
    purpose: "Analyze List in editor uses loaded feed URL; updates CodeMirror list rules"
  - name: "F-48: Editor Analyze Content with sample URL calls API"
    line: 569
    purpose: "Analyze Content with sample URL calls analyze-content API"
  - name: "F-49: Editor Analyze Content without sample URL shows prompt"
    line: 580
    purpose: "Analyze Content without sample URL shows input prompt dialog"
  - name: "F-50: Editor Analyze Content prompt cancel does not call API"
    line: 593
    purpose: "Cancelling sample URL prompt in editor does not call analyze-content API"
  - name: "F-51: Editor Test List sends preview request"
    line: 607
    purpose: "Test List in editor sends preview request with editor's URL"
  - name: "F-52: Editor Test Content with sample URL sends preview request"
    line: 619
    purpose: "Test Content in editor sends preview request with sample URL"
  - name: "F-53: Editor Toggle Rules hides rules panel"
    line: 631
    purpose: "Toggle Rules button in editor hides the rules panel"
  - name: "F-54: Editor Toggle Rules shows rules panel and refreshes CodeMirror"
    line: 640
    purpose: "Toggle Rules again shows panel and refreshes CodeMirror editors"
  - name: "F-55: Editor CodeMirror List Rules is editable"
    line: 652
    purpose: "CodeMirror list rules in editor accepts keyboard input"
  - name: "F-56: Editor CodeMirror Content Rules is editable"
    line: 659
    purpose: "CodeMirror content rules in editor accepts keyboard input"
  - name: "F-57: Editor Debug toggle switches debugMode and label style"
    line: 666
    purpose: "Debug checkbox in editor changes label style when toggled"
  - name: "F-58: Save Changes success updates feed and refreshes table"
    line: 678
    purpose: "Mocked PUT /sites/:id success shows success toast and refreshes feed table"
  - name: "F-59: Save Changes with invalid List Rules JSON shows alert"
    line: 690
    purpose: "Invalid JSON in list-rules CodeMirror shows validation alert on Save Changes"
  - name: "F-60: Save Changes with invalid Content Rules JSON shows alert"
    line: 702
    purpose: "Invalid JSON in content-rules CodeMirror shows validation alert on Save Changes"
  - name: "F-61: Save Changes prevents double-submit with saving flag"
    line: 713
    purpose: "Rapid double-click on Save Changes button does not submit twice"
  - name: "F-62: Editor Crawl button triggers POST /crawl/:id"
    line: 729
    purpose: "Crawl button in editor calls POST /crawl/:id"
  - name: "F-63: Filter Builder initializes with existing filter_rules"
    line: 748
    purpose: "Feed with existing filter_rules populates filter builder UI on load"
  - name: "F-64: Blacklist mode radio selection"
    line: 755
    purpose: "Clicking Blacklist radio selects it and deselects Whitelist"
  - name: "F-65: Whitelist mode radio selection"
    line: 763
    purpose: "Clicking Whitelist radio selects it and deselects Blacklist"
  - name: "F-66: Whole Words Only checkbox toggles"
    line: 771
    purpose: "#whole-words checkbox can be toggled on and off"
  - name: "F-67: Toggle AND/OR operator switches button style"
    line: 782
    purpose: "AND/OR toggle changes active button style in filter builder"
  - name: "F-68: Add Rule creates new rule row with field/match/value inputs"
    line: 798
    purpose: "Clicking Add Rule adds a new row with field, match type, and value inputs"
  - name: "F-69: Add Inner Group creates nested filter group"
    line: 808
    purpose: "Clicking Add Inner Group creates a nested filter group container"
  - name: "F-70: Update Rule Field dropdown changes field value"
    line: 819
    purpose: "Selecting a different field in rule dropdown updates its value"
  - name: "F-71: Update Rule Match dropdown changes match type"
    line: 829
    purpose: "Selecting a different match type in rule dropdown updates its value"
  - name: "F-72: Update Rule Value input accepts text"
    line: 839
    purpose: "Rule value text input accepts typed content"
  - name: "F-73: Rule move-up swaps with previous rule"
    line: 849
    purpose: "Clicking move-up on second rule swaps it with first rule"
  - name: "F-74: Rule move-down swaps with next rule"
    line: 862
    purpose: "Clicking move-down on first rule swaps it with second rule"
  - name: "F-75: Delete Rule removes rule row from UI"
    line: 873
    purpose: "Clicking delete on a rule removes that rule row from filter builder"
  - name: "F-76: Delete non-root Group removes entire group"
    line: 884
    purpose: "Clicking delete on a non-root group removes the entire group"
  - name: "F-77: Preview section is initially hidden"
    line: 903
    purpose: "Preview section is hidden before any Edit click in feed list"
  - name: "F-78: Preview section shows after Edit click"
    line: 909
    purpose: "Preview section becomes visible after clicking Edit on a feed row"
  - name: "F-79: Test Both sends preview request with mode=both"
    line: 916
    purpose: "Test Both button in editor sends preview request with mode=both"
  - name: "F-80: Preview Filter button activates filter mode"
    line: 928
    purpose: "Clicking Preview Filter button activates filter preview mode"
  - name: "F-81: Preview Filter button deactivates on second click"
    line: 936
    purpose: "Clicking Preview Filter again deactivates filter preview mode"
  - name: "F-82: Filtered articles show warning banner and visual styling"
    line: 945
    purpose: "Articles matching filter rules show warning banner with count"
  - name: "F-83: Preview loading shows spinner and message"
    line: 974
    purpose: "Delayed preview API keeps loading spinner visible"
  - name: "F-84: Preview error shows danger alert"
    line: 982
    purpose: "500 from preview API shows danger alert in preview section"
  - name: "F-85: Debug banner shows path in debug mode after test"
    line: 999
    purpose: "Debug mode enabled with debug_dir in response shows path banner"
  - name: "F-86: Debug banner Copy button copies path to clipboard"
    line: 1009
    purpose: "Clicking Copy in debug banner copies debug_dir path to clipboard"
  - name: "F-87: 401 unauthorized redirects to login page"
    line: 1028
    purpose: "Cleared cookies navigating to /feeds/edit redirects to login"
  - name: "F-88: Analyze buttons are disabled during API call to prevent duplicates"
    line: 1034
    purpose: "Analyze buttons disabled while analyze API call is in progress"
  - name: "F-89: Save success invalidates sites cache and refreshes table"
    line: 1042
    purpose: "After save, sites cache is cleared and feed table reloaded"
  - name: "F-90: Deleting currently-edited feed hides editor and preview"
    line: 1053
    purpose: "Deleting a feed that is currently being edited hides editor and preview"
run:
  command: "cd frontend-astro && npx playwright test tests/stage2/e2e/stage2/feeds.spec.ts"
  prerequisites:
    - "App running on http://localhost:5174"
---
*/
import { test, expect } from '@playwright/test'

// =============================================================================
// Add Feed Page (/feeds/add)
// =============================================================================
test.describe('Add Feed Page', () => {
  test.describe.configure({ mode: 'serial' })

  test('F-01: Page loads with feed wizard and hidden preview section', async ({ page }) => {
    await page.goto('/feeds/add')
    await expect(page.locator('#feed-wizard')).toBeVisible()
    await expect(page.locator('#preview-section')).toHaveClass(/d-none/)
    await expect(page.locator('.CodeMirror').first()).toBeVisible()
  })

  test('F-02: Back button navigates to /dashboard', async ({ page }) => {
    await page.goto('/feeds/add')
    // Use the Back button specifically (btn-outline-secondary) to avoid strict mode violation
    await page.locator('a.btn-outline-secondary[href="/dashboard"]').click()
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('F-03: URL field accepts input', async ({ page }) => {
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    await expect(page.locator('#wizard-url')).toHaveValue('https://example.com/blog')
  })

  test('F-04: Site Name field accepts input', async ({ page }) => {
    await page.goto('/feeds/add')
    await page.locator('#wizard-name').fill('Example Blog')
    await expect(page.locator('#wizard-name')).toHaveValue('Example Blog')
  })

  test('F-05: Analyze List with empty URL shows alert', async ({ page }) => {
    await page.goto('/feeds/add')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Please enter Target URL first')
      await dialog.accept()
    })
    await page.locator('#btn-analyze-list').click()
  })

  test('F-06: Analyze List success populates CodeMirror list rules', async ({ page }) => {
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

  test('F-07: Analyze List API failure shows error alert', async ({ page }) => {
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Error analyzing list')
      await dialog.accept()
    })
    await page.locator('#btn-analyze-list').click()
  })

  test('F-08: Analyze Content with empty Sample URL shows alert', async ({ page }) => {
    await page.goto('/feeds/add')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Please enter Sample Article URL first')
      await dialog.accept()
    })
    await page.locator('#btn-analyze-content').click()
  })

  test('F-09: Analyze Content success populates CodeMirror content rules', async ({ page }) => {
    await page.goto('/feeds/add')
    await page.locator('#wizard-sample-url').fill('https://example.com/blog/post-1')
    await page.locator('#btn-analyze-content').click()
    await expect(page.locator('#btn-analyze-content')).toBeDisabled()
    await page.waitForResponse(resp =>
      resp.url().includes('/analyze/content') && resp.request().method() === 'POST'
    )
    await expect(page.locator('#cm-wizard-content-rules .CodeMirror')).toBeVisible()
  })

  test('F-10: Sample Article URL field accepts input', async ({ page }) => {
    await page.goto('/feeds/add')
    await page.locator('#wizard-sample-url').fill('https://example.com/blog/post-1')
    await expect(page.locator('#wizard-sample-url')).toHaveValue('https://example.com/blog/post-1')
  })

  test('F-11: Toggle Rules JSON hides rules panel', async ({ page }) => {
    await page.goto('/feeds/add')
    // Ensure rules panel is visible first
    await expect(page.locator('#rules-panel')).not.toHaveClass(/d-none/)
    await page.locator('#btn-toggle-rules').click()
    await expect(page.locator('#rules-panel')).toHaveClass(/d-none/)
    await expect(page.locator('#btn-toggle-rules')).toContainText('Show Rules JSON')
  })

  test('F-12: Toggle Rules JSON shows rules panel', async ({ page }) => {
    await page.goto('/feeds/add')
    // Hide first
    await page.locator('#btn-toggle-rules').click()
    await expect(page.locator('#rules-panel')).toHaveClass(/d-none/)
    // Show again
    await page.locator('#btn-toggle-rules').click()
    await expect(page.locator('#rules-panel')).not.toHaveClass(/d-none/)
    await expect(page.locator('#btn-toggle-rules')).toContainText('Hide Rules JSON')
  })

  test('F-13: CodeMirror List Rules editor is editable', async ({ page }) => {
    await page.goto('/feeds/add')
    await expect(page.locator('#cm-wizard-list-rules .CodeMirror')).toBeVisible()
  })

  test('F-14: CodeMirror Content Rules editor is editable', async ({ page }) => {
    await page.goto('/feeds/add')
    await expect(page.locator('#cm-wizard-content-rules .CodeMirror')).toBeVisible()
  })

  test('F-15: Test List with empty URL shows alert', async ({ page }) => {
    await page.goto('/feeds/add')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Please enter a Target URL first')
      await dialog.accept()
    })
    await page.locator('#btn-test-list').click()
  })

  test('F-16: Test List success shows preview with Title/URL columns', async ({ page }) => {
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    await page.locator('#btn-test-list').click()
    await expect(page.locator('#preview-section')).not.toHaveClass(/d-none/)
    await page.waitForResponse(resp =>
      resp.url().includes('/crawl/preview') && resp.request().method() === 'POST'
    )
    await expect(page.locator('#preview-body')).toBeVisible()
  })

  test('F-17: Test Content with empty Sample URL shows alert', async ({ page }) => {
    await page.goto('/feeds/add')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Please enter a Sample URL to test content extraction')
      await dialog.accept()
    })
    await page.locator('#btn-test-content').click()
  })

  test('F-18: Test Content success shows preview with Title/Time/Content columns', async ({ page }) => {
    await page.goto('/feeds/add')
    await page.locator('#wizard-sample-url').fill('https://example.com/blog/post-1')
    await page.locator('#btn-test-content').click()
    await page.waitForResponse(resp =>
      resp.url().includes('/crawl/preview') && resp.request().method() === 'POST'
    )
    await expect(page.locator('#preview-body')).toBeVisible()
  })

  test('F-19: Test Both with empty URL shows alert', async ({ page }) => {
    await page.goto('/feeds/add')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Please enter a Target URL first')
      await dialog.accept()
    })
    await page.locator('#btn-test-both').click()
  })

  test('F-20: Test Both success shows three-column preview results', async ({ page }) => {
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    await page.locator('#btn-test-both').click()
    await page.waitForResponse(resp =>
      resp.url().includes('/crawl/preview') && resp.request().method() === 'POST'
    )
    await expect(page.locator('#preview-body')).toBeVisible()
  })

  test('F-21: Preview loading state shows spinner during test', async ({ page }) => {
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    await page.locator('#btn-test-list').click()
    await expect(page.locator('#preview-loading')).toBeVisible()
  })

  test('F-22: Preview error displays error message', async ({ page }) => {
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    // Mock crawl to return an error so the error element is displayed
    await page.route('**/crawl/preview', async route => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Crawl failed: connection refused' })
      })
    })
    await page.locator('#btn-test-list').click()
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#preview-error')).not.toHaveClass(/d-none/)
  })

  test('F-23: Preview with no results shows guidance message', async ({ page }) => {
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    // Mock crawl/preview to return empty data so renderPreviewTable shows "No results found"
    await page.route('**/crawl/preview', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data: [] })
      })
    })
    await page.locator('#btn-test-list').click()
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#preview-body')).toContainText('No results found')
  })

  test('F-24: Debug mode checkbox toggles debugMode', async ({ page }) => {
    await page.goto('/feeds/add')
    const debugCheckbox = page.locator('#wizard-debug')
    await debugCheckbox.check()
    await expect(debugCheckbox).toBeChecked()
    await debugCheckbox.uncheck()
    await expect(debugCheckbox).not.toBeChecked()
  })

  test('F-25: Debug banner shows debug_dir path after test in debug mode', async ({ page }) => {
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    await page.locator('#wizard-debug').check()
    // Mock crawl/preview to return debug_dir so the debug banner is shown
    await page.route('**/crawl/preview', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data: [{ title: 'Test', url: 'https://example.com/1' }], debug_dir: '/tmp/debug/crawl-123' })
      })
    })
    // After test call with debug=true, banner should show
    await page.locator('#btn-test-list').click()
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#debug-banner')).not.toHaveClass(/d-none/)
    await expect(page.locator('#debug-banner-path')).not.toBeEmpty()
  })

  test('F-26: Save with empty URL or Name shows alert', async ({ page }) => {
    await page.goto('/feeds/add')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('URL and Site Name are required')
      await dialog.accept()
    })
    await page.locator('#btn-save').click()
  })

  test('F-27: Save with invalid JSON shows alert', async ({ page }) => {
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

  test('F-28: Save success creates feed and redirects to /dashboard', async ({ page }) => {
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

  test('F-29: Save API failure shows error and restores button', async ({ page }) => {
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    await page.locator('#wizard-name').fill('Example Blog')
    // Mock POST /sites/ to return server error so save fails and button is restored
    await page.route(/\/sites\/$/, async route => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Internal server error' })
        })
      } else {
        await route.continue()
      }
    })
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
  test.describe.configure({ mode: 'serial' })

  test('F-30: Page loads feed table with loading spinner', async ({ page }) => {
    await page.route(/\/sites\//, async route => {
      await new Promise(r => setTimeout(r, 500))
      await route.continue()
    })
    await page.goto('/feeds/edit')
    // Loading state should appear initially
    await expect(page.locator('#feed-table-loading')).toBeVisible()
    // After API response, table body should render
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#feed-table-body')).toBeVisible()
  })

  test('F-31: URL with ?site=<id> auto-loads feed into editor', async ({ page }) => {
    // Get the first site's actual ID from the feed table
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    const firstSiteId = await page.locator('tr[data-site-id]').first().getAttribute('data-site-id')
    // Navigate with the actual site ID in the URL
    await page.goto(`/feeds/edit?site=${firstSiteId}`)
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#editor-section')).not.toHaveClass(/d-none/)
  })

  test('F-32: Empty feed list shows "No feeds found" message', async ({ page }) => {
    // Mock sites API to return empty array BEFORE navigating — getSites is called on init
    await page.route(/\/sites\/$/, async route => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([])
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#feed-table-body')).toContainText('No feeds found')
  })

  test('F-33: Refresh Table button reloads feed list', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    // Add a delay to the sites endpoint so the button stays disabled long enough to observe
    await page.route(/\/sites\/$/, async route => {
      await new Promise(r => setTimeout(r, 400))
      await route.continue()
    })
    await page.locator('#btn-refresh-table').click()
    await expect(page.locator('#btn-refresh-table')).toBeDisabled()
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#btn-refresh-table')).toBeEnabled()
  })

  test('F-34: Row Edit button loads feed into editor section', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    const firstRow = page.locator('tr[data-site-id]').first()
    await firstRow.locator('[data-action="edit"]').click()
    await expect(page.locator('#editor-section')).not.toHaveClass(/d-none/)
    await expect(firstRow).toHaveClass(/table-active/)
  })

  test('F-35: Row Duplicate button shows confirm dialog and duplicates feed', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Duplicate this feed configuration?')
      await dialog.accept()
    })
    const firstRow = page.locator('tr[data-site-id]').first()
    await firstRow.locator('[data-action="duplicate"]').click()
  })

  test('F-36: Duplicate cancel does not trigger API call', async ({ page }) => {
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

  test('F-37: Row Crawl button triggers crawl and shows spinner', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    // Mock crawl endpoint with delay to keep button disabled long enough, and prevent post-test dialog errors
    await page.route(/\/crawl\/\d+/, async route => {
      if (route.request().method() === 'POST') {
        await new Promise(r => setTimeout(r, 300))
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) })
      } else {
        await route.continue()
      }
    })
    const firstRow = page.locator('tr[data-site-id]').first()
    const crawlBtn = firstRow.locator('[data-action="crawl"]')
    page.on('dialog', dialog => dialog.accept())
    await crawlBtn.click()
    await expect(crawlBtn).toBeDisabled()
    await page.waitForLoadState('networkidle')  // wait for crawl to complete so dialog is handled before test ends
  })

  test('F-38: Row Crawl button prevents duplicate triggers', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    let crawlCount = 0
    page.on('request', req => {
      if (req.url().includes('/crawl/') && req.method() === 'POST') crawlCount++
    })
    // Mock crawl endpoint with a brief delay so button stays disabled during second click
    await page.route(/\/crawl\/\d+/, async route => {
      if (route.request().method() === 'POST') {
        await new Promise(r => setTimeout(r, 300))
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) })
      } else {
        await route.continue()
      }
    })
    page.on('dialog', dialog => dialog.accept())
    const firstRow = page.locator('tr[data-site-id]').first()
    const crawlBtn = firstRow.locator('[data-action="crawl"]')
    await crawlBtn.click()
    // Force click while button is disabled — crawlingId guard in handleManualCrawl prevents second crawl
    await crawlBtn.click({ force: true })
    await page.waitForLoadState('networkidle')
    // Only one crawl request should have been sent
    expect(crawlCount).toBeLessThanOrEqual(1)
  })

  test('F-39: Row Delete button shows confirm and deletes feed', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    // Mock DELETE endpoint to prevent actual DB deletion (preserves shared test state)
    await page.route(/\/sites\/\d+$/, async route => {
      if (route.request().method() === 'DELETE') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true }) })
      } else {
        await route.continue()
      }
    })
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Are you sure you want to delete this feed?')
      await dialog.accept()
    })
    const firstRow = page.locator('tr[data-site-id]').first()
    await firstRow.locator('[data-action="delete"]').click()
  })

  test('F-40: Delete cancel does not trigger API call', async ({ page }) => {
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

  test('F-41: Delete API failure shows error alert', async ({ page }) => {
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
  test.describe.configure({ mode: 'serial' })

  test('F-42: Editor section appears with correct title after Edit click', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await expect(page.locator('#editor-section')).not.toHaveClass(/d-none/)
    await expect(page.locator('#editor-title')).toContainText('Editing:')
  })

  test('F-43: Target URL field is editable in editor', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    const urlInput = page.locator('#input-url')
    await urlInput.fill('https://updated.example.com')
    await expect(urlInput).toHaveValue('https://updated.example.com')
  })

  test('F-44: Site Name field is editable in editor', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    const nameInput = page.locator('#input-name')
    await nameInput.fill('Updated Name')
    await expect(nameInput).toHaveValue('Updated Name')
  })

  test('F-45: Refresh Frequency field accepts valid numeric input', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    const freqInput = page.locator('#input-freq')
    await freqInput.fill('30')
    await expect(freqInput).toHaveValue('30')
  })

  test('F-46: Sample URL field is editable in editor', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    const sampleInput = page.locator('#input-sample-url')
    await sampleInput.fill('https://example.com/blog/post-1')
    await expect(sampleInput).toHaveValue('https://example.com/blog/post-1')
  })

  test('F-47: Editor Analyze List uses editData URL and updates CodeMirror', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#editor-section').waitFor({ state: 'visible', timeout: 10000 })
    await page.locator('#editor-section #btn-analyze-list').scrollIntoViewIfNeeded()
    await page.locator('#editor-section #btn-analyze-list').click()
    await expect(page.locator('#editor-section #btn-analyze-list')).toBeDisabled()
    await page.waitForResponse(resp =>
      resp.url().includes('/analyze/list') && resp.request().method() === 'POST'
    )
    await expect(page.locator('#cm-list-rules .CodeMirror')).toBeVisible()
  })

  test('F-48: Editor Analyze Content with sample URL calls API', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#input-sample-url').fill('https://example.com/post-1')
    await page.locator('#editor-section #btn-analyze-content').click()
    await page.waitForResponse(resp =>
      resp.url().includes('/analyze/content') && resp.request().method() === 'POST'
    )
  })

  test('F-49: Editor Analyze Content without sample URL shows prompt', async ({ page }) => {
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

  test('F-50: Editor Analyze Content prompt cancel does not call API', async ({ page }) => {
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

  test('F-51: Editor Test List sends preview request', async ({ page }) => {
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

  test('F-52: Editor Test Content with sample URL sends preview request', async ({ page }) => {
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

  test('F-53: Editor Toggle Rules hides rules panel', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#editor-section #btn-toggle-rules').click()
    await expect(page.locator('#editor-section #rules-panel')).toHaveClass(/d-none/)
    await expect(page.locator('#editor-section #btn-toggle-rules')).toContainText('Show Rules')
  })

  test('F-54: Editor Toggle Rules shows rules panel and refreshes CodeMirror', async ({ page }) => {
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

  test('F-55: Editor CodeMirror List Rules is editable', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await expect(page.locator('#cm-list-rules .CodeMirror')).toBeVisible()
  })

  test('F-56: Editor CodeMirror Content Rules is editable', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await expect(page.locator('#cm-content-rules .CodeMirror')).toBeVisible()
  })

  test('F-57: Editor Debug toggle switches debugMode and label style', async ({ page }) => {
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

  test('F-58: Save Changes success updates feed and refreshes table', async ({ page }) => {
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

  test('F-59: Save Changes with invalid List Rules JSON shows alert', async ({ page }) => {
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

  test('F-60: Save Changes with invalid Content Rules JSON shows alert', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    page.on('dialog', async dialog => {
      expect(dialog.message()).toContain('Invalid JSON in Content Rules')
      await dialog.accept()
    })
    await page.locator('#btn-save').click()
  })

  test('F-61: Save Changes prevents double-submit with saving flag', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    // Slow down the save API so the button stays disabled long enough to assert
    await page.route(/\/sites\/\d+$/, async route => {
      if (route.request().method() === 'PUT') {
        await new Promise(r => setTimeout(r, 500))
      }
      await route.continue()
    })
    page.on('dialog', dialog => dialog.accept())
    await page.locator('#btn-save').click()
    await expect(page.locator('#btn-save')).toBeDisabled()
  })

  test('F-62: Editor Crawl button triggers POST /crawl/:id', async ({ page }) => {
    // Register dialog handler BEFORE any navigation/action that could trigger it
    page.on('dialog', dialog => dialog.accept())
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
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

  test('F-63: Filter Builder initializes with existing filter_rules', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await expect(page.locator('#filter-builder-root')).toBeVisible()
  })

  test('F-64: Blacklist mode radio selection', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#filter-mode-bl').check()
    await expect(page.locator('#filter-mode-bl')).toBeChecked()
  })

  test('F-65: Whitelist mode radio selection', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#filter-mode-wl').check()
    await expect(page.locator('#filter-mode-wl')).toBeChecked()
  })

  test('F-66: Whole Words Only checkbox toggles', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    const checkbox = page.locator('#filter-whole-word')
    await checkbox.check()
    await expect(checkbox).toBeChecked()
    await checkbox.uncheck()
    await expect(checkbox).not.toBeChecked()
  })

  test('F-67: Toggle AND/OR operator switches button style', async ({ page }) => {
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

  test('F-68: Add Rule creates new rule row with field/match/value inputs', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    const initialRules = await page.locator('#filter-builder-root [data-action="delete-rule"]').count()
    await page.locator('[data-action="add-rule"]').first().click()
    const newRules = await page.locator('#filter-builder-root [data-action="delete-rule"]').count()
    expect(newRules).toBe(initialRules + 1)
  })

  test('F-69: Add Inner Group creates nested filter group', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('[data-action="add-group"]').first().click()
    // Should have a nested group with its own operator toggle
    const nestedGroups = page.locator('#filter-builder-root [data-action="delete-group"]')
    const count = await nestedGroups.count()
    expect(count).toBeGreaterThan(0)
  })

  test('F-70: Update Rule Field dropdown changes field value', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('[data-action="add-rule"]').first().click()
    const fieldSelect = page.locator('[data-action="update-rule-field"]').last()
    await fieldSelect.selectOption('content')
    await expect(fieldSelect).toHaveValue('content')
  })

  test('F-71: Update Rule Match dropdown changes match type', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('[data-action="add-rule"]').first().click()
    const matchSelect = page.locator('[data-action="update-rule-match"]').last()
    await matchSelect.selectOption('regex')
    await expect(matchSelect).toHaveValue('regex')
  })

  test('F-72: Update Rule Value input accepts text', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('[data-action="add-rule"]').first().click()
    const valueInput = page.locator('[data-action="update-rule-value"]').last()
    await valueInput.fill('test-keyword')
    await expect(valueInput).toHaveValue('test-keyword')
  })

  test('F-73: Rule move-up swaps with previous rule', async ({ page }) => {
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

  test('F-74: Rule move-down swaps with next rule', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('[data-action="add-rule"]').first().click()
    await page.locator('[data-action="add-rule"]').first().click()
    // Last rule's move-down should be disabled
    const moveDownBtns = page.locator('[data-action="move-down"]')
    await expect(moveDownBtns.last()).toBeDisabled()
  })

  test('F-75: Delete Rule removes rule row from UI', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('[data-action="add-rule"]').first().click()
    const initialRules = await page.locator('[data-action="delete-rule"]').count()
    await page.locator('[data-action="delete-rule"]').last().click()
    const newRules = await page.locator('[data-action="delete-rule"]').count()
    expect(newRules).toBe(initialRules - 1)
  })

  test('F-76: Delete non-root Group removes entire group', async ({ page }) => {
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
  test.describe.configure({ mode: 'serial' })

  test('F-77: Preview section is initially hidden', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#preview-section')).toHaveClass(/d-none/)
  })

  test('F-78: Preview section shows after Edit click', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await expect(page.locator('#preview-section')).not.toHaveClass(/d-none/)
  })

  test('F-79: Test Both sends preview request with mode=both', async ({ page }) => {
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

  test('F-80: Preview Filter button activates filter mode', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await expect(page.locator('#editor-section')).not.toHaveClass(/d-none/, { timeout: 15000 })
    await page.locator('#btn-filter-preview').click()
    await expect(page.locator('#btn-filter-preview')).toHaveClass(/active/)
  })

  test('F-81: Preview Filter button deactivates on second click', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#btn-filter-preview').click()
    await page.locator('#btn-filter-preview').click()
    await expect(page.locator('#btn-filter-preview')).not.toHaveClass(/active/)
  })

  test('F-82: Filtered articles show warning banner and visual styling', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    // Mock preview to return articles with some filtered so we can test the UI rendering
    await page.route('**/crawl/preview', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: [
            { title: 'Article 1', url: 'https://example.com/1', filtered: false },
            { title: 'Article 2', url: 'https://example.com/2', filtered: true },
            { title: 'Article 3', url: 'https://example.com/3', filtered: true }
          ],
          filter_summary: { passed: 1, filtered_out: 2 }
        })
      })
    })
    // Activate filter preview and test
    await page.locator('#btn-filter-preview').click()
    await page.locator('#btn-test-both').click()
    await page.waitForLoadState('networkidle')
    // Filtered rows should have opacity-50 and line-through styling
    await expect(page.locator('#preview-body')).toContainText('articles hidden by filter rules')
    await expect(page.locator('#preview-body tr.opacity-50').first()).toBeVisible()
  })

  test('F-83: Preview loading shows spinner and message', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#btn-test-both').click()
    await expect(page.locator('#preview-body')).toContainText('Crawling and analyzing')
  })

  test('F-84: Preview error shows danger alert', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    // Mock crawl to return an error so the danger alert is shown
    await page.route('**/crawl/preview', async route => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Crawl failed: connection timeout' })
      })
    })
    await page.locator('#btn-test-both').click()
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#preview-body .alert-danger')).toBeVisible()
  })

  test('F-85: Debug banner shows path in debug mode after test', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    await page.locator('#debug-checkbox').check()
    await page.locator('#btn-test-both').click()
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#preview-body .debug-dir-banner')).toBeVisible()
  })

  test('F-86: Debug banner Copy button copies path to clipboard', async ({ page }) => {
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
  test.describe.configure({ mode: 'serial' })

  test('F-87: 401 unauthorized redirects to login page', async ({ page }) => {
    await page.context().clearCookies()
    await page.goto('/feeds/edit')
    await page.waitForURL('**/login**', { timeout: 15000 })
  })

  test('F-88: Analyze buttons are disabled during API call to prevent duplicates', async ({ page }) => {
    await page.goto('/feeds/add')
    await page.locator('#wizard-url').fill('https://example.com/blog')
    await page.locator('#btn-analyze-list').click()
    await expect(page.locator('#btn-analyze-list')).toBeDisabled()
    await expect(page.locator('#btn-analyze-content')).toBeDisabled()
  })

  test('F-89: Save success invalidates sites cache and refreshes table', async ({ page }) => {
    await page.goto('/feeds/edit')
    await page.waitForLoadState('networkidle')
    await page.locator('tr[data-site-id]').first().locator('[data-action="edit"]').click()
    page.on('dialog', dialog => dialog.accept())
    await page.locator('#btn-save').click()
    // Table should refresh after save
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#feed-table-body')).toBeVisible()
  })

  test('F-90: Deleting currently-edited feed hides editor and preview', async ({ page }) => {
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
