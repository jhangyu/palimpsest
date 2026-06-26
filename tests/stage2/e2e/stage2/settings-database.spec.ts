/*
---
name: settings-database
description: "Stage 2 E2E: /settings/database — DB status card (spinner/status/migrations), export card (format/checkboxes/download), import card (dropzone/preview/confirm/import), auth redirect"
stage: stage2
type: playwright
target:
  layer: frontend
  domain: settings-database
spec_doc: docs/test-specs/stage2/s2-08-settings-database.md
test_file: tests/stage2/e2e/stage2/settings-database.spec.ts
tests:
  - name: "S2.8.01 Page load shows DB status spinner"
    line: 19
    purpose: "Delayed DB status API keeps loading spinner visible on page load"
  - name: "S2.8.02 Status table populated after API response"
    line: 29
    purpose: "DB status table rows populated after API response"
  - name: "S2.8.03 DB version badge shows schema_version"
    line: 40
    purpose: "Version badge shows schema_version value from DB status API"
  - name: "S2.8.04 Last migration time displayed"
    line: 49
    purpose: "Last migration timestamp displayed in DB status section"
  - name: "S2.8.05 No pending migrations: alert hidden"
    line: 65
    purpose: "Mocked DB status with no pending migrations hides pending-migrations alert"
  - name: "S2.8.06 Pending migrations: alert visible with count and list"
    line: 87
    purpose: "Mocked pending migrations shows alert with count and migration list"
  - name: "S2.8.07 Run Migrations success"
    line: 112
    purpose: "Mocked POST /db/migrate success shows success alert and reloads status"
  - name: "S2.8.08 Run Migrations failure"
    line: 145
    purpose: "500 from POST /db/migrate shows error alert"
  - name: "S2.8.09 DB status API error: badge turns red"
    line: 182
    purpose: "500 from DB status API changes version badge to red/danger color"
  - name: "S2.8.10 Default checkboxes: sites + articles checked"
    line: 198
    purpose: "On export card load, sites and articles checkboxes are checked by default"
  - name: "S2.8.11 Default format is ZIP"
    line: 209
    purpose: "ZIP format radio is selected by default in export section"
  - name: "S2.8.12 No checkbox selected shows warning"
    line: 221
    purpose: "Unchecking all export checkboxes and clicking Export shows validation warning"
  - name: "S2.8.13 Export ZIP format download"
    line: 230
    purpose: "Mocked ZIP export triggers file download with .zip extension"
  - name: "S2.8.14 Export JSON format download"
    line: 244
    purpose: "Selecting JSON format and mocked export triggers file download"
  - name: "S2.8.15 Export multiple tables"
    line: 258
    purpose: "Checking multiple export tables calls export API with all selected tables"
  - name: "S2.8.16 Export button loading state"
    line: 274
    purpose: "Export button disabled and shows loading state during export API call"
  - name: "S2.8.17 Export API error"
    line: 286
    purpose: "500 from export API shows error alert"
  - name: "S2.8.18 Import buttons disabled on load"
    line: 301
    purpose: "Preview and Import buttons disabled until a file is selected"
  - name: "S2.8.19 Click dropzone opens file picker"
    line: 307
    purpose: "Clicking import dropzone triggers file input click"
  - name: "S2.8.20 Drag over dropzone adds border-primary"
    line: 321
    purpose: "Dragging file over dropzone adds border-primary CSS class"
  - name: "S2.8.21 Drag leave removes border-primary"
    line: 328
    purpose: "Dragging file away from dropzone removes border-primary CSS class"
  - name: "S2.8.22 Select valid .json file updates UI"
    line: 343
    purpose: "Selecting a valid .json file enables buttons and shows file name in UI"
  - name: "S2.8.23 Select valid .zip file updates UI"
    line: 358
    purpose: "Selecting a valid .zip file enables buttons and shows file name in UI"
  - name: "S2.8.24 Select invalid file type shows warning"
    line: 371
    purpose: "Selecting non-json/zip file shows invalid file type warning"
  - name: "S2.8.25 Clear file resets UI"
    line: 382
    purpose: "Clicking Clear resets file selection and disables buttons"
  - name: "S2.8.26 Conflict resolution default is skip"
    line: 401
    purpose: "Conflict resolution 'skip' radio is selected by default"
  - name: "S2.8.27 Preview button triggers API and shows results"
    line: 419
    purpose: "Clicking Preview calls /db/import/preview and shows preview results"
  - name: "S2.8.28 Preview warnings displayed"
    line: 449
    purpose: "Mocked preview with warnings shows warning messages in preview section"
  - name: "S2.8.29 Preview incompatible file shows warning"
    line: 474
    purpose: "Mocked preview incompatible response shows incompatible warning banner"
  - name: "S2.8.30 Preview button loading state"
    line: 497
    purpose: "Preview button shows loading state during preview API call"
  - name: "S2.8.31 Preview API error"
    line: 518
    purpose: "500 from preview API shows error alert"
  - name: "S2.8.32 Confirm dialog cancel aborts import"
    line: 541
    purpose: "Cancelling import confirm dialog does not call import API"
  - name: "S2.8.33 Import with mode=skip success"
    line: 577
    purpose: "Mocked import with skip conflict mode shows success and import summary"
  - name: "S2.8.34 Import with mode=overwrite success"
    line: 636
    purpose: "Mocked import with overwrite conflict mode shows success and import summary"
  - name: "S2.8.35 Import button loading state"
    line: 694
    purpose: "Import button shows loading state during import API call"
  - name: "S2.8.36 Import API error"
    line: 734
    purpose: "500 from import API shows error alert"
  - name: "S2.8.37 DB status reloads after successful import"
    line: 772
    purpose: "After successful import, DB status API is called again to refresh status"
  - name: "S2.8.38 Unauthenticated access redirects to login"
    line: 838
    purpose: "Cleared cookies navigating to /settings/database redirects to login"
run:
  command: "cd frontend-astro && npx playwright test tests/stage2/e2e/stage2/settings-database.spec.ts"
  prerequisites:
    - "App running on http://localhost:5174"
---
*/
import { test, expect } from '@playwright/test'

// =============================================================================
// Card A — Database Status: Loading
// =============================================================================
test.describe('Database Status — Loading', () => {

  test('S2.8.01 Page load shows DB status spinner', async ({ page }) => {
    await page.route('**/settings/database/status', async route => {
      await new Promise(r => setTimeout(r, 500))
      await route.continue()
    })
    await page.goto('/settings/database')
    await expect(page.locator('#db-status-loading')).toBeVisible()
    await expect(page.locator('#db-status-content')).not.toBeVisible()
  })

  test('S2.8.02 Status table populated after API response', async ({ page }) => {
    await page.goto('/settings/database')
    await page.waitForResponse(resp =>
      resp.url().includes('/settings/database/status') && resp.request().method() === 'GET'
    )
    await expect(page.locator('#db-status-loading')).not.toBeVisible()
    await expect(page.locator('#db-status-content')).toBeVisible()
    await expect(page.locator('#db-tables-body tr')).not.toHaveCount(0)
    await expect(page.locator('#db-version-badge')).not.toHaveText('Loading...')
  })

  test('S2.8.03 DB version badge shows schema_version', async ({ page }) => {
    await page.goto('/settings/database')
    await page.waitForResponse(resp =>
      resp.url().includes('/settings/database/status') && resp.request().method() === 'GET'
    )
    const badgeText = await page.locator('#db-version-badge').textContent()
    expect(badgeText).toMatch(/^(\d{8}_\d{3}|\d+\.\d+\.\d+)$/)
  })

  test('S2.8.04 Last migration time displayed', async ({ page }) => {
    await page.goto('/settings/database')
    await page.waitForResponse(resp =>
      resp.url().includes('/settings/database/status') && resp.request().method() === 'GET'
    )
    const text = await page.locator('#db-last-migration').textContent()
    expect(text === 'Never' || /\d/.test(text ?? '')).toBe(true)
  })
})

// =============================================================================
// Card A — Database Status: Migrations
// =============================================================================
test.describe('Database Status — Migrations', () => {
  test.describe.configure({ mode: 'serial' })

  test('S2.8.05 No pending migrations: alert hidden', async ({ page }) => {
    // Mock API to return no pending migrations
    await page.route('**/settings/database/status', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          schema_version: '0.1.0',
          app_version: '0.1.0',
          tables: [{ name: 'sites', row_count: 5 }],
          pending_migrations: [],
          last_migration_at: null
        })
      })
    )
    await page.goto('/settings/database')
    await page.waitForResponse(resp =>
      resp.url().includes('/settings/database/status') && resp.request().method() === 'GET'
    )
    await expect(page.locator('#db-migration-alert')).not.toBeVisible()
  })

  test('S2.8.06 Pending migrations: alert visible with count and list', async ({ page }) => {
    // Mock API to return pending_migrations with data
    await page.route('**/settings/database/status', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          schema_version: '20250101_001',
          app_version: '0.1.0',
          tables: [{ name: 'sites', row_count: 5 }],
          pending_migrations: [
            { version: '20250102_001', description: 'Add new column' },
            { version: '20250103_001', description: 'Create index' }
          ],
          last_migration_at: '2025-01-01T00:00:00Z'
        })
      })
    )
    await page.goto('/settings/database')
    await expect(page.locator('#db-migration-alert')).toBeVisible()
    await expect(page.locator('#db-migration-count')).toHaveText('2')
    await expect(page.locator('.db-migration-list')).toContainText('20250102_001')
    await expect(page.locator('#btn-run-migrations')).toBeVisible()
  })

  test('S2.8.07 Run Migrations success', async ({ page }) => {
    // Mock status API with pending migrations
    await page.route('**/settings/database/status', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          schema_version: '20250101_001',
          app_version: '0.1.0',
          tables: [{ name: 'sites', row_count: 5 }],
          pending_migrations: [
            { version: '20250102_001', description: 'Add column' }
          ],
          last_migration_at: null
        })
      })
    )
    // Mock migrate API
    await page.route('**/settings/database/migrate', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          applied: [{ version: '20250102_001', description: 'Add column' }]
        })
      })
    )
    await page.goto('/settings/database')
    await expect(page.locator('#btn-run-migrations')).toBeVisible()
    await page.locator('#btn-run-migrations').click()
    await expect(page.locator('#db-status-error')).toContainText(/success/i)
  })

  test('S2.8.08 Run Migrations failure', async ({ page }) => {
    // Mock status API with pending migrations
    await page.route('**/settings/database/status', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          schema_version: '20250101_001',
          app_version: '0.1.0',
          tables: [{ name: 'sites', row_count: 5 }],
          pending_migrations: [
            { version: '20250102_001', description: 'Add column' }
          ],
          last_migration_at: null
        })
      })
    )
    // Mock migrate API to return error
    await page.route('**/settings/database/migrate', route =>
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Migration failed' })
      })
    )
    await page.goto('/settings/database')
    await expect(page.locator('#btn-run-migrations')).toBeVisible()
    await page.locator('#btn-run-migrations').click()
    await expect(page.locator('#db-status-error .alert-danger')).toBeVisible()
  })
})

// =============================================================================
// Card A — Database Status: Error Handling
// =============================================================================
test.describe('Database Status — Error Handling', () => {

  test('S2.8.09 DB status API error: badge turns red', async ({ page }) => {
    await page.route('**/settings/database/status', route =>
      route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"Server error"}' })
    )
    await page.goto('/settings/database')
    await expect(page.locator('#db-version-badge')).toHaveText('Error')
    await expect(page.locator('#db-version-badge')).toHaveClass(/bg-danger/)
    await expect(page.locator('#db-status-error .alert-danger')).toBeVisible()
  })
})

// =============================================================================
// Card B — Export: Default State
// =============================================================================
test.describe('Export — Default State', () => {

  test('S2.8.10 Default checkboxes: sites + articles checked', async ({ page }) => {
    await page.goto('/settings/database')
    await expect(page.locator('#export-sites')).toBeChecked()
    await expect(page.locator('#export-articles')).toBeChecked()
    await expect(page.locator('#export-crawl-attempts')).not.toBeChecked()
    await expect(page.locator('#export-rss-events')).not.toBeChecked()
    await expect(page.locator('#export-users')).not.toBeChecked()
    await expect(page.locator('#export-roles')).not.toBeChecked()
    await expect(page.locator('#export-user-roles')).not.toBeChecked()
  })

  test('S2.8.11 Default format is ZIP', async ({ page }) => {
    await page.goto('/settings/database')
    await expect(page.locator('#export-format-zip')).toBeChecked()
  })
})

// =============================================================================
// Card B — Export: Functionality
// =============================================================================
test.describe('Export — Functionality', () => {
  test.describe.configure({ mode: 'serial' })

  test('S2.8.12 No checkbox selected shows warning', async ({ page }) => {
    await page.goto('/settings/database')
    // Uncheck all checkboxes
    await page.locator('#export-sites').uncheck()
    await page.locator('#export-articles').uncheck()
    await page.locator('#btn-export').click()
    await expect(page.locator('#export-status')).toContainText('Please select at least one table to export.')
  })

  test('S2.8.13 Export ZIP format download', async ({ page }) => {
    await page.goto('/settings/database')
    // Ensure only sites checked
    await page.locator('#export-articles').uncheck()
    await expect(page.locator('#export-sites')).toBeChecked()
    await expect(page.locator('#export-format-zip')).toBeChecked()

    const downloadPromise = page.waitForEvent('download')
    await page.locator('#btn-export').click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toMatch(/palimpsest-export-\d{4}-\d{2}-\d{2}\.zip/)
    await expect(page.locator('#export-status')).toContainText('Export downloaded')
  })

  test('S2.8.14 Export JSON format download', async ({ page }) => {
    await page.goto('/settings/database')
    // Select only articles, choose JSON format
    await page.locator('#export-sites').uncheck()
    await expect(page.locator('#export-articles')).toBeChecked()
    await page.locator('#export-format-json').check()

    const downloadPromise = page.waitForEvent('download')
    await page.locator('#btn-export').click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toMatch(/\.json$/)
    await expect(page.locator('#export-status')).toContainText('Export downloaded')
  })

  test('S2.8.15 Export multiple tables', async ({ page }) => {
    await page.goto('/settings/database')
    await expect(page.locator('#export-sites')).toBeChecked()
    await expect(page.locator('#export-articles')).toBeChecked()

    let requestUrl = ''
    page.on('request', req => {
      if (req.url().includes('/settings/database/export')) {
        requestUrl = req.url()
      }
    })
    await page.locator('#btn-export').click()
    expect(requestUrl).toContain('tables=sites')
    expect(requestUrl).toContain('articles')
  })

  test('S2.8.16 Export button loading state', async ({ page }) => {
    await page.goto('/settings/database')
    // Delay export response to observe loading state
    await page.route('**/settings/database/export**', async route => {
      await new Promise(r => setTimeout(r, 1000))
      await route.fulfill({ status: 200, body: '{}' })
    })
    await page.locator('#btn-export').click()
    await expect(page.locator('#btn-export')).toBeDisabled()
    await expect(page.locator('#btn-export .spinner-border')).toBeVisible()
  })

  test('S2.8.17 Export API error', async ({ page }) => {
    await page.route('**/settings/database/export**', route =>
      route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"Export failed"}' })
    )
    await page.goto('/settings/database')
    await page.locator('#btn-export').click()
    await expect(page.locator('#export-status .alert-danger')).toBeVisible()
  })
})

// =============================================================================
// Card C — Import: Initial State
// =============================================================================
test.describe('Import — Initial State', () => {

  test('S2.8.18 Import buttons disabled on load', async ({ page }) => {
    await page.goto('/settings/database')
    await expect(page.locator('#btn-preview-import')).toBeDisabled()
    await expect(page.locator('#btn-import')).toBeDisabled()
  })

  test('S2.8.19 Click dropzone opens file picker', async ({ page }) => {
    await page.goto('/settings/database')
    const fileInputClicked = page.evaluate(() => {
      return new Promise<boolean>(resolve => {
        const input = document.getElementById('import-file-input')
        if (input) {
          input.addEventListener('click', () => resolve(true), { once: true })
        }
      })
    })
    await page.locator('#import-dropzone').click()
    expect(await fileInputClicked).toBe(true)
  })

  test('S2.8.20 Drag over dropzone adds border-primary', async ({ page }) => {
    await page.goto('/settings/database')
    const dropzone = page.locator('#import-dropzone')
    await dropzone.dispatchEvent('dragover', { bubbles: true })
    await expect(dropzone).toHaveClass(/border-primary/)
  })

  test('S2.8.21 Drag leave removes border-primary', async ({ page }) => {
    await page.goto('/settings/database')
    const dropzone = page.locator('#import-dropzone')
    await dropzone.dispatchEvent('dragover', { bubbles: true })
    await expect(dropzone).toHaveClass(/border-primary/)
    await dropzone.dispatchEvent('dragleave', { bubbles: true })
    await expect(dropzone).not.toHaveClass(/border-primary/)
  })
})

// =============================================================================
// Card C — Import: File Selection
// =============================================================================
test.describe('Import — File Selection', () => {

  test('S2.8.22 Select valid .json file updates UI', async ({ page }) => {
    await page.goto('/settings/database')
    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'backup.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{"tables":[]}')
    })
    await expect(page.locator('#import-file-info')).toBeVisible()
    await expect(page.locator('#import-file-name')).toContainText('backup.json')
    await expect(page.locator('#import-options')).toBeVisible()
    await expect(page.locator('#btn-preview-import')).toBeEnabled()
    await expect(page.locator('#btn-import')).toBeDisabled()
  })

  test('S2.8.23 Select valid .zip file updates UI', async ({ page }) => {
    await page.goto('/settings/database')
    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'backup.zip',
      mimeType: 'application/zip',
      buffer: Buffer.from('PK\x03\x04')
    })
    await expect(page.locator('#import-file-info')).toBeVisible()
    await expect(page.locator('#import-options')).toBeVisible()
    await expect(page.locator('#btn-preview-import')).toBeEnabled()
  })

  test('S2.8.24 Select invalid file type shows warning', async ({ page }) => {
    await page.goto('/settings/database')
    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'data.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from('col1,col2')
    })
    await expect(page.locator('#import-result')).toContainText('Only .json and .zip files are accepted.')
  })

  test('S2.8.25 Clear file resets UI', async ({ page }) => {
    await page.goto('/settings/database')
    // First select a valid file
    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'backup.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{"tables":[]}')
    })
    await expect(page.locator('#import-file-info')).toBeVisible()
    // Now clear
    await page.locator('#btn-clear-file').click()
    await expect(page.locator('#import-file-info')).not.toBeVisible()
    await expect(page.locator('#import-options')).not.toBeVisible()
    await expect(page.locator('#btn-preview-import')).toBeDisabled()
    await expect(page.locator('#btn-import')).toBeDisabled()
    await expect(page.locator('#import-preview')).not.toBeVisible()
  })

  test('S2.8.26 Conflict resolution default is skip', async ({ page }) => {
    await page.goto('/settings/database')
    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'backup.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{"tables":[]}')
    })
    await expect(page.locator('#import-mode-skip')).toBeChecked()
  })
})

// =============================================================================
// Card C — Import: Preview
// =============================================================================
test.describe('Import — Preview', () => {
  test.describe.configure({ mode: 'serial' })

  test('S2.8.27 Preview button triggers API and shows results', async ({ page }) => {
    await page.route('**/settings/database/import/preview', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          compatible: true,
          warnings: [],
          tables: [
            { name: 'sites', total: 10, new: 8, conflicts: 2 },
            { name: 'articles', total: 50, new: 45, conflicts: 5 }
          ]
        })
      })
    )
    await page.goto('/settings/database')
    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'backup.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{"tables":[]}')
    })
    await page.locator('#btn-preview-import').click()
    await expect(page.locator('#import-preview')).toBeVisible()
    await expect(page.locator('#import-preview-body tr')).toHaveCount(2)
    await expect(page.locator('#import-preview-body')).toContainText('sites')
    await expect(page.locator('#import-preview-body')).toContainText('articles')
    await expect(page.locator('#btn-import')).toBeEnabled()
  })

  test('S2.8.28 Preview warnings displayed', async ({ page }) => {
    await page.route('**/settings/database/import/preview', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          compatible: true,
          warnings: ['Missing column: tags', 'Schema version mismatch'],
          tables: [{ name: 'sites', total: 5, new: 5, conflicts: 0 }]
        })
      })
    )
    await page.goto('/settings/database')
    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'backup.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{"tables":[]}')
    })
    await page.locator('#btn-preview-import').click()
    await expect(page.locator('#import-warnings .alert-warning')).toBeVisible()
    await expect(page.locator('#import-warnings')).toContainText('Missing column: tags')
    await expect(page.locator('#import-warnings')).toContainText('Schema version mismatch')
  })

  test('S2.8.29 Preview incompatible file shows warning', async ({ page }) => {
    await page.route('**/settings/database/import/preview', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          compatible: false,
          warnings: [],
          tables: [{ name: 'sites', total: 5, new: 5, conflicts: 0 }]
        })
      })
    )
    await page.goto('/settings/database')
    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'backup.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{"tables":[]}')
    })
    await page.locator('#btn-preview-import').click()
    await expect(page.locator('#import-result')).toContainText('This file may not be compatible with the current schema.')
  })

  test('S2.8.30 Preview button loading state', async ({ page }) => {
    await page.route('**/settings/database/import/preview', async route => {
      await new Promise(r => setTimeout(r, 1000))
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ compatible: true, warnings: [], tables: [] })
      })
    })
    await page.goto('/settings/database')
    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'backup.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{"tables":[]}')
    })
    await page.locator('#btn-preview-import').click()
    await expect(page.locator('#btn-preview-import')).toBeDisabled()
    await expect(page.locator('#btn-preview-import .spinner-border')).toBeVisible()
  })

  test('S2.8.31 Preview API error', async ({ page }) => {
    await page.route('**/settings/database/import/preview', route =>
      route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"Preview failed"}' })
    )
    await page.goto('/settings/database')
    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'backup.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{"tables":[]}')
    })
    await page.locator('#btn-preview-import').click()
    await expect(page.locator('#import-result .alert-danger')).toBeVisible()
    await expect(page.locator('#btn-import')).toBeDisabled()
  })
})

// =============================================================================
// Card C — Import: Execution
// =============================================================================
test.describe('Import — Execution', () => {
  test.describe.configure({ mode: 'serial' })

  test('S2.8.32 Confirm dialog cancel aborts import', async ({ page }) => {
    // Mock preview API
    await page.route('**/settings/database/import/preview', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          compatible: true,
          warnings: [],
          tables: [{ name: 'sites', total: 5, new: 5, conflicts: 0 }]
        })
      })
    )
    await page.goto('/settings/database')
    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'backup.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{"tables":[]}')
    })
    await page.locator('#btn-preview-import').click()
    await expect(page.locator('#btn-import')).toBeEnabled()

    // Intercept confirm dialog and dismiss
    page.on('dialog', dialog => dialog.dismiss())

    let importCalled = false
    page.on('request', req => {
      if (req.url().includes('/settings/database/import') && req.method() === 'POST' && !req.url().includes('preview')) {
        importCalled = true
      }
    })
    await page.locator('#btn-import').click()
    expect(importCalled).toBe(false)
  })

  test('S2.8.33 Import with mode=skip success', async ({ page }) => {
    // Mock preview API
    await page.route('**/settings/database/import/preview', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          compatible: true,
          warnings: [],
          tables: [{ name: 'sites', total: 10, new: 8, conflicts: 2 }]
        })
      })
    )
    // Mock import API
    let importUrl = ''
    await page.route('**/settings/database/import?**', route => {
      importUrl = route.request().url()
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          tables: [{ name: 'sites', imported: 8, skipped: 2, overwritten: 0 }]
        })
      })
    })
    // Mock status reload
    await page.route('**/settings/database/status', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          schema_version: '20250101_001',
          app_version: '0.1.0',
          tables: [{ name: 'sites', row_count: 13 }],
          pending_migrations: [],
          last_migration_at: null
        })
      })
    )

    await page.goto('/settings/database')
    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'backup.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{"tables":[]}')
    })
    await page.locator('#btn-preview-import').click()
    await expect(page.locator('#btn-import')).toBeEnabled()
    await expect(page.locator('#import-mode-skip')).toBeChecked()

    // Accept confirm dialog
    page.on('dialog', dialog => dialog.accept())
    await page.locator('#btn-import').click()

    await expect(page.locator('#import-result .alert-success')).toBeVisible()
    expect(importUrl).toContain('mode=skip')
  })

  test('S2.8.34 Import with mode=overwrite success', async ({ page }) => {
    // Mock preview API
    await page.route('**/settings/database/import/preview', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          compatible: true,
          warnings: [],
          tables: [{ name: 'sites', total: 10, new: 8, conflicts: 2 }]
        })
      })
    )
    // Mock import API
    let importUrl = ''
    await page.route('**/settings/database/import?**', route => {
      importUrl = route.request().url()
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          tables: [{ name: 'sites', imported: 10, skipped: 0, overwritten: 2 }]
        })
      })
    })
    await page.route('**/settings/database/status', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          schema_version: '20250101_001',
          app_version: '0.1.0',
          tables: [{ name: 'sites', row_count: 15 }],
          pending_migrations: [],
          last_migration_at: null
        })
      })
    )

    await page.goto('/settings/database')
    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'backup.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{"tables":[]}')
    })
    // Switch to overwrite mode
    await page.locator('#import-mode-overwrite').check()
    await page.locator('#btn-preview-import').click()
    await expect(page.locator('#btn-import')).toBeEnabled()

    page.on('dialog', dialog => dialog.accept())
    await page.locator('#btn-import').click()

    await expect(page.locator('#import-result .alert-success')).toBeVisible()
    expect(importUrl).toContain('mode=overwrite')
  })

  test('S2.8.35 Import button loading state', async ({ page }) => {
    // Mock preview API
    await page.route('**/settings/database/import/preview', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          compatible: true,
          warnings: [],
          tables: [{ name: 'sites', total: 5, new: 5, conflicts: 0 }]
        })
      })
    )
    // Mock import API with delay
    await page.route('**/settings/database/import?**', async route => {
      await new Promise(r => setTimeout(r, 1000))
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ tables: [{ name: 'sites', imported: 5, skipped: 0, overwritten: 0 }] })
      })
    })

    await page.goto('/settings/database')
    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'backup.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{"tables":[]}')
    })
    await page.locator('#btn-preview-import').click()
    await expect(page.locator('#btn-import')).toBeEnabled()

    page.on('dialog', dialog => dialog.accept())
    await page.locator('#btn-import').click()

    await expect(page.locator('#btn-import')).toBeDisabled()
    await expect(page.locator('#btn-import .spinner-border')).toBeVisible()
  })

  test('S2.8.36 Import API error', async ({ page }) => {
    // Mock preview API
    await page.route('**/settings/database/import/preview', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          compatible: true,
          warnings: [],
          tables: [{ name: 'sites', total: 5, new: 5, conflicts: 0 }]
        })
      })
    )
    // Mock import API error
    await page.route('**/settings/database/import?**', route =>
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Import failed: disk full' })
      })
    )

    await page.goto('/settings/database')
    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'backup.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{"tables":[]}')
    })
    await page.locator('#btn-preview-import').click()
    await expect(page.locator('#btn-import')).toBeEnabled()

    page.on('dialog', dialog => dialog.accept())
    await page.locator('#btn-import').click()

    await expect(page.locator('#import-result .alert-danger')).toBeVisible()
  })

  test('S2.8.37 DB status reloads after successful import', async ({ page }) => {
    let statusCallCount = 0
    // Mock status API — track call count
    await page.route('**/settings/database/status', route => {
      statusCallCount++
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          schema_version: '20250101_001',
          app_version: '0.1.0',
          tables: [{ name: 'sites', row_count: statusCallCount > 1 ? 15 : 5 }],
          pending_migrations: [],
          last_migration_at: null
        })
      })
    })
    // Mock preview API
    await page.route('**/settings/database/import/preview', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          compatible: true,
          warnings: [],
          tables: [{ name: 'sites', total: 10, new: 10, conflicts: 0 }]
        })
      })
    )
    // Mock import API
    await page.route('**/settings/database/import?**', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          tables: [{ name: 'sites', imported: 10, skipped: 0, overwritten: 0 }]
        })
      })
    )

    await page.goto('/settings/database')
    await expect(page.locator('#db-tables-body')).toContainText('5')

    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'backup.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{"tables":[]}')
    })
    await page.locator('#btn-preview-import').click()
    await expect(page.locator('#btn-import')).toBeEnabled()

    page.on('dialog', dialog => dialog.accept())
    await page.locator('#btn-import').click()
    await expect(page.locator('#import-result .alert-success')).toBeVisible()

    // DB status should have been reloaded with updated count
    await expect(page.locator('#db-tables-body')).toContainText('15')
  })
})

// =============================================================================
// Authentication Guard
// =============================================================================
test.describe('Authentication Guard', () => {

  test('S2.8.38 Unauthenticated access redirects to login', async ({ page }) => {
    await page.context().clearCookies()
    await page.goto('/settings/database')
    await page.waitForURL('**/login**', { timeout: 15000 })
  })
})
