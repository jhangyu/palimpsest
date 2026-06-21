/**
 * S2-08: Settings Database — Playwright Tests
 * Spec: docs/test-specs/s2-08-settings-database.md
 *
 * Covers: /settings/database page — Database Status (Card A),
 * Export Data (Card B), Import Data (Card C), migration management,
 * and auth redirect.
 *
 * Tests requiring authentication are marked test.skip until session fixture lands.
 * Run: npx playwright test tests/stage2/settings-database.spec.ts
 */
import { test, expect } from '@playwright/test'

// =============================================================================
// Card A — Database Status: Loading
// =============================================================================
test.describe('Database Status — Loading', () => {

  test.skip('S2.8.01 Page load shows DB status spinner', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/database')
    await expect(page.locator('#db-status-loading')).toBeVisible()
    await expect(page.locator('#db-status-content')).not.toBeVisible()
  })

  test.skip('S2.8.02 Status table populated after API response', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/database')
    await page.waitForResponse(resp =>
      resp.url().includes('/settings/database/status') && resp.request().method() === 'GET'
    )
    await expect(page.locator('#db-status-loading')).not.toBeVisible()
    await expect(page.locator('#db-status-content')).toBeVisible()
    await expect(page.locator('#db-tables-body tr')).not.toHaveCount(0)
    await expect(page.locator('#db-version-badge')).not.toHaveText('Loading...')
  })

  test.skip('S2.8.03 DB version badge shows schema_version', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/database')
    await page.waitForResponse(resp =>
      resp.url().includes('/settings/database/status') && resp.request().method() === 'GET'
    )
    const badgeText = await page.locator('#db-version-badge').textContent()
    expect(badgeText).toMatch(/^\d{8}_\d{3}$/)
  })

  test.skip('S2.8.04 Last migration time displayed', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.05 No pending migrations: alert hidden', async ({ page }) => {
    // TODO: requires auth session fixture
    // API returns pending_migrations=[]
    await page.goto('/settings/database')
    await page.waitForResponse(resp =>
      resp.url().includes('/settings/database/status') && resp.request().method() === 'GET'
    )
    await expect(page.locator('#db-migration-alert')).not.toBeVisible()
  })

  test.skip('S2.8.06 Pending migrations: alert visible with count and list', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.07 Run Migrations success', async ({ page }) => {
    // TODO: requires auth session fixture
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
    await expect(page.locator('#db-status-error')).toContainText('success')
  })

  test.skip('S2.8.08 Run Migrations failure', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.09 DB status API error: badge turns red', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.10 Default checkboxes: sites + articles checked', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/database')
    await expect(page.locator('#export-sites')).toBeChecked()
    await expect(page.locator('#export-articles')).toBeChecked()
    await expect(page.locator('#export-crawl-attempts')).not.toBeChecked()
    await expect(page.locator('#export-rss-events')).not.toBeChecked()
    await expect(page.locator('#export-users')).not.toBeChecked()
    await expect(page.locator('#export-roles')).not.toBeChecked()
    await expect(page.locator('#export-user-roles')).not.toBeChecked()
  })

  test.skip('S2.8.11 Default format is ZIP', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/database')
    await expect(page.locator('#export-format-zip')).toBeChecked()
  })
})

// =============================================================================
// Card B — Export: Functionality
// =============================================================================
test.describe('Export — Functionality', () => {

  test.skip('S2.8.12 No checkbox selected shows warning', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/database')
    // Uncheck all checkboxes
    await page.locator('#export-sites').uncheck()
    await page.locator('#export-articles').uncheck()
    await page.locator('#btn-export').click()
    await expect(page.locator('#export-status')).toContainText('Please select at least one table to export.')
  })

  test.skip('S2.8.13 Export ZIP format download', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/database')
    // Ensure only sites checked
    await page.locator('#export-articles').uncheck()
    await expect(page.locator('#export-sites')).toBeChecked()
    await expect(page.locator('#export-format-zip')).toBeChecked()

    const downloadPromise = page.waitForEvent('download')
    await page.locator('#btn-export').click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toMatch(/palimpsest-export-\d{4}-\d{2}-\d{2}\.zip/)
    await expect(page.locator('#export-status')).toContainText('success')
  })

  test.skip('S2.8.14 Export JSON format download', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/database')
    // Select only articles, choose JSON format
    await page.locator('#export-sites').uncheck()
    await expect(page.locator('#export-articles')).toBeChecked()
    await page.locator('#export-format-json').check()

    const downloadPromise = page.waitForEvent('download')
    await page.locator('#btn-export').click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toMatch(/\.json$/)
    await expect(page.locator('#export-status')).toContainText('success')
  })

  test.skip('S2.8.15 Export multiple tables', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.16 Export button loading state', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.17 Export API error', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.18 Import buttons disabled on load', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/database')
    await expect(page.locator('#btn-preview-import')).toBeDisabled()
    await expect(page.locator('#btn-import')).toBeDisabled()
  })

  test.skip('S2.8.19 Click dropzone opens file picker', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.20 Drag over dropzone adds border-primary', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/database')
    const dropzone = page.locator('#import-dropzone')
    await dropzone.dispatchEvent('dragover', { bubbles: true })
    await expect(dropzone).toHaveClass(/border-primary/)
  })

  test.skip('S2.8.21 Drag leave removes border-primary', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.22 Select valid .json file updates UI', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.23 Select valid .zip file updates UI', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.24 Select invalid file type shows warning', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/settings/database')
    const fileInput = page.locator('#import-file-input')
    await fileInput.setInputFiles({
      name: 'data.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from('col1,col2')
    })
    await expect(page.locator('#import-result')).toContainText('Only .json and .zip files are accepted.')
  })

  test.skip('S2.8.25 Clear file resets UI', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.26 Conflict resolution default is skip', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.27 Preview button triggers API and shows results', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.28 Preview warnings displayed', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.29 Preview incompatible file shows warning', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.30 Preview button loading state', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.31 Preview API error', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.32 Confirm dialog cancel aborts import', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.33 Import with mode=skip success', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.34 Import with mode=overwrite success', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.35 Import button loading state', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.36 Import API error', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.37 DB status reloads after successful import', async ({ page }) => {
    // TODO: requires auth session fixture
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

  test.skip('S2.8.38 Unauthenticated access redirects to login', async ({ page }) => {
    // TODO: requires verifying redirect behavior when NOT logged in
    await page.goto('/settings/database')
    await expect(page).toHaveURL(/\/authentication\/modern\/login/)
  })
})
