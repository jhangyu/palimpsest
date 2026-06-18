/**
 * database.ts — Page handlers for Database management settings
 *
 * Exports:
 *   initDatabasePage() — DB status, export, import handlers
 */

import { api } from './api'

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function showStatus(
  elementId: string,
  message: string,
  type: 'success' | 'danger' | 'warning' | 'info'
): void {
  const el = document.getElementById(elementId)
  if (!el) return
  el.innerHTML = `<div class="alert alert-${type} mb-0 py-2">${message}</div>`
  el.style.removeProperty('display')
}

function clearStatus(elementId: string): void {
  const el = document.getElementById(elementId)
  if (!el) return
  el.innerHTML = ''
}

function setButtonLoading(btn: HTMLButtonElement, loading: boolean): void {
  if (loading) {
    btn.disabled = true
    btn.dataset.originalText = btn.innerHTML
    btn.innerHTML =
      '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Loading...'
  } else {
    btn.disabled = false
    if (btn.dataset.originalText) {
      btn.innerHTML = btn.dataset.originalText
    }
  }
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

export function initDatabasePage(): void {
  // Check if we're on the database page by looking for a key element
  const versionBadge = document.getElementById('db-version-badge')
  if (!versionBadge) return

  loadDatabaseStatus()
  bindExportHandlers()
  bindImportHandlers()

  const migrateBtn = document.getElementById('btn-run-migrations') as HTMLButtonElement | null
  if (migrateBtn) {
    migrateBtn.addEventListener('click', async () => {
      setButtonLoading(migrateBtn, true)
      try {
        const result = await api.runMigrations()
        const count = result.applied?.length ?? 0
        showStatus('db-status-error', `<i class="ri-check-line me-1"></i>Successfully applied ${count} migration(s).`, 'success')
        await loadDatabaseStatus()
      } catch (err) {
        showStatus('db-status-error', `<i class="ri-error-warning-line me-1"></i>${escapeHtml(err instanceof Error ? err.message : 'Migration failed.')}`, 'danger')
      } finally {
        setButtonLoading(migrateBtn, false)
      }
    })
  }
}

// ---------------------------------------------------------------------------
// DB Status
// ---------------------------------------------------------------------------

async function loadDatabaseStatus(): Promise<void> {
  const spinner = document.getElementById('db-status-loading')
  const content = document.getElementById('db-status-content')
  const errorEl = document.getElementById('db-status-error')

  // Debug: log which API endpoint is being called
  if (typeof window !== 'undefined') {
    console.debug('[Database] Initializing database page')
  }

  // Show spinner, hide previous content
  spinner?.style.removeProperty('display')
  if (content) content.style.display = 'none'
  if (errorEl) errorEl.style.display = 'none'

  try {
    const status = await api.getDatabaseStatus()

    // Version badge
    const versionBadge = document.getElementById('db-version-badge')
    if (versionBadge) {
      versionBadge.textContent = status.schema_version
    }

    // Tables body
    const tablesBody = document.getElementById('db-tables-body')
    if (tablesBody) {
      if (status.tables.length === 0) {
        tablesBody.innerHTML = `
          <tr>
            <td colspan="2" class="text-muted text-center py-3">No tables found.</td>
          </tr>`
      } else {
        tablesBody.innerHTML = status.tables
          .map(
            (t: { name: string; row_count: number }) => `
          <tr>
            <td>${escapeHtml(t.name)}</td>
            <td class="text-end">${t.row_count.toLocaleString()}</td>
          </tr>`
          )
          .join('')
      }
    }

    // Last migration time
    const lastMigrationEl = document.getElementById('db-last-migration')
    if (lastMigrationEl) {
      lastMigrationEl.textContent = status.last_migration_at
        ? new Date(status.last_migration_at).toLocaleString()
        : 'Never'
    }

    // Pending migrations alert
    const migrationAlert = document.getElementById('db-migration-alert')
    if (migrationAlert) {
      if (status.pending_migrations.length > 0) {
        const list = status.pending_migrations
          .map(
            (m: { version: string; description: string }) =>
              `<li><code>${escapeHtml(m.version)}</code> — ${escapeHtml(m.description)}</li>`
          )
          .join('')
        const alertBody = migrationAlert.querySelector('.db-migration-list')
        if (alertBody) alertBody.innerHTML = `<ul class="mb-0">${list}</ul>`
        migrationAlert.style.removeProperty('display')
      } else {
        migrationAlert.style.display = 'none'
      }
    }

    // Hide spinner, show content
    if (spinner) spinner.style.display = 'none'
    if (content) content.style.removeProperty('display')
  } catch (err) {
    if (spinner) spinner.style.display = 'none'
    // Update version badge to show error state
    const versionBadge = document.getElementById('db-version-badge')
    if (versionBadge) {
      versionBadge.textContent = 'Error'
      versionBadge.className = 'badge bg-danger'
    }
    console.error('[Database] Failed to load status:', err)
    if (errorEl) {
      errorEl.innerHTML = `
        <div class="alert alert-danger">
          <i class="ri-error-warning-line me-2"></i>
          ${escapeHtml(err instanceof Error ? err.message : 'Failed to load database status.')}
        </div>`
      errorEl.style.removeProperty('display')
    }
  }
}

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

function bindExportHandlers(): void {
  const exportBtn = document.getElementById('btn-export') as HTMLButtonElement | null
  if (!exportBtn) return

  exportBtn.addEventListener('click', async () => {
    // Collect checked table checkboxes
    const checked = Array.from(
      document.querySelectorAll<HTMLInputElement>(
        'input[type="checkbox"][id^="export-"]:checked'
      )
    ).map((cb) => cb.value)

    if (checked.length === 0) {
      showStatus('export-status', 'Please select at least one table to export.', 'warning')
      return
    }

    const formatInput = document.querySelector<HTMLInputElement>(
      'input[name="export-format"]:checked'
    )
    const format = (formatInput?.value ?? 'zip') as 'json' | 'zip'

    clearStatus('export-status')
    setButtonLoading(exportBtn, true)

    try {
      await api.exportDatabase(checked, format)
      const formatLabel = format === 'zip' ? 'ZIP' : 'JSON'
      showStatus('export-status', `<i class="ri-check-line me-1"></i>Export downloaded as ${formatLabel}.`, 'success')
    } catch (err) {
      showStatus(
        'export-status',
        `<i class="ri-error-warning-line me-1"></i>${escapeHtml(
          err instanceof Error ? err.message : 'Export failed.'
        )}`,
        'danger'
      )
    } finally {
      setButtonLoading(exportBtn, false)
    }
  })
}

// ---------------------------------------------------------------------------
// Import
// ---------------------------------------------------------------------------

function bindImportHandlers(): void {
  const dropzone = document.getElementById('import-dropzone')
  const fileInput = document.getElementById('import-file-input') as HTMLInputElement | null
  const fileInfo = document.getElementById('import-file-info')
  const optionsEl = document.getElementById('import-options')
  const clearBtn = document.getElementById('btn-clear-file') as HTMLButtonElement | null
  const previewBtn = document.getElementById('btn-preview-import') as HTMLButtonElement | null
  const importBtn = document.getElementById('btn-import') as HTMLButtonElement | null
  const previewEl = document.getElementById('import-preview')
  const previewBody = document.getElementById('import-preview-body')
  const resultEl = document.getElementById('import-result')
  const warningsEl = document.getElementById('import-warnings')

  if (!dropzone || !fileInput) return

  let selectedFile: File | null = null

  // --- Drag & Drop ---

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault()
    dropzone.classList.add('border-primary')
  })

  dropzone.addEventListener('dragenter', (e) => {
    e.preventDefault()
    dropzone.classList.add('border-primary')
  })

  dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('border-primary')
  })

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault()
    dropzone.classList.remove('border-primary')
    const file = e.dataTransfer?.files?.[0]
    if (file) handleFileSelected(file)
  })

  // --- Click on dropzone ---

  dropzone.addEventListener('click', () => {
    fileInput.click()
  })

  // --- File input change ---

  fileInput.addEventListener('change', () => {
    const file = fileInput.files?.[0]
    if (file) handleFileSelected(file)
  })

  // --- Handle file selection ---

  function handleFileSelected(file: File): void {
    const ext = file.name.toLowerCase()
    if (!ext.endsWith('.json') && !ext.endsWith('.zip')) {
      showImportStatus('Only .json and .zip files are accepted.', 'warning')
      return
    }

    selectedFile = file

    // Show file info
    if (fileInfo) {
      fileInfo.textContent = `Selected: ${file.name} (${formatBytes(file.size)})`
      fileInfo.style.removeProperty('display')
    }

    // Show conflict resolution options
    if (optionsEl) optionsEl.style.removeProperty('display')

    // Enable preview button
    if (previewBtn) previewBtn.disabled = false

    // Reset preview/result sections
    if (previewEl) previewEl.style.display = 'none'
    if (resultEl) resultEl.innerHTML = ''
    if (importBtn) importBtn.disabled = true
  }

  // --- Clear file ---

  clearBtn?.addEventListener('click', () => {
    selectedFile = null
    fileInput.value = ''

    if (fileInfo) {
      fileInfo.textContent = ''
      fileInfo.style.display = 'none'
    }
    if (optionsEl) optionsEl.style.display = 'none'
    if (previewEl) previewEl.style.display = 'none'
    if (resultEl) resultEl.innerHTML = ''
    if (warningsEl) {
      warningsEl.innerHTML = ''
      warningsEl.style.display = 'none'
    }
    if (previewBtn) previewBtn.disabled = true
    if (importBtn) importBtn.disabled = true
  })

  // --- Preview import ---

  previewBtn?.addEventListener('click', async () => {
    if (!selectedFile) return

    setButtonLoading(previewBtn, true)
    if (warningsEl) {
      warningsEl.innerHTML = ''
      warningsEl.style.display = 'none'
    }

    try {
      const preview = await api.previewImport(selectedFile)

      // Show warnings
      if (preview.warnings.length > 0 && warningsEl) {
        const list = preview.warnings
          .map((w: string) => `<li>${escapeHtml(w)}</li>`)
          .join('')
        warningsEl.innerHTML = `
          <div class="alert alert-warning">
            <strong>Warnings:</strong>
            <ul class="mb-0 mt-1">${list}</ul>
          </div>`
        warningsEl.style.removeProperty('display')
      }

      // Compatibility badge
      if (!preview.compatible) {
        showImportStatus(
          '<i class="ri-error-warning-line me-1"></i>This file may not be compatible with the current schema.',
          'warning'
        )
      }

      // Fill preview table
      if (previewBody) {
        if (preview.tables.length === 0) {
          previewBody.innerHTML = `
            <tr>
              <td colspan="4" class="text-muted text-center py-3">No tables in file.</td>
            </tr>`
        } else {
          previewBody.innerHTML = preview.tables
            .map(
              (t: { name: string; total: number; new: number; conflicts: number }) => `
            <tr>
              <td>${escapeHtml(t.name)}</td>
              <td class="text-end">${t.total.toLocaleString()}</td>
              <td class="text-end text-success">${t.new.toLocaleString()}</td>
              <td class="text-end text-warning">${t.conflicts.toLocaleString()}</td>
            </tr>`
            )
            .join('')
        }
      }

      // Show preview section, enable import
      if (previewEl) previewEl.style.removeProperty('display')
      if (importBtn) importBtn.disabled = false
    } catch (err) {
      showImportStatus(
        `<i class="ri-error-warning-line me-1"></i>${escapeHtml(
          err instanceof Error ? err.message : 'Preview failed.'
        )}`,
        'danger'
      )
    } finally {
      setButtonLoading(previewBtn, false)
    }
  })

  // --- Import ---

  importBtn?.addEventListener('click', async () => {
    if (!selectedFile) return
    if (!window.confirm('Are you sure you want to import? This will modify your database.')) return

    // Get selected conflict resolution mode
    const modeInput = document.querySelector<HTMLInputElement>(
      'input[name="import-mode"]:checked'
    )
    const mode = (modeInput?.value ?? 'skip') as 'skip' | 'overwrite'

    setButtonLoading(importBtn, true)
    if (resultEl) resultEl.innerHTML = ''

    try {
      const result = await api.importDatabase(selectedFile, mode)

      const rows = result.tables
        .map(
          (t: { name: string; imported: number; skipped: number; overwritten: number }) => `
        <tr>
          <td>${escapeHtml(t.name)}</td>
          <td class="text-end text-success">${t.imported.toLocaleString()}</td>
          <td class="text-end text-muted">${t.skipped.toLocaleString()}</td>
          <td class="text-end text-warning">${t.overwritten.toLocaleString()}</td>
        </tr>`
        )
        .join('')

      if (resultEl) {
        resultEl.style.removeProperty('display')
        resultEl.innerHTML = `
          <div class="alert alert-success mt-3">
            <strong><i class="ri-check-line me-1"></i>Import completed successfully.</strong>
            <table class="table table-sm mb-0 mt-2">
              <thead>
                <tr>
                  <th>Table</th>
                  <th class="text-end">Imported</th>
                  <th class="text-end">Skipped</th>
                  <th class="text-end">Overwritten</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          </div>`
      }

      // Reload DB status to reflect new counts
      loadDatabaseStatus()
    } catch (err) {
      if (resultEl) {
        resultEl.style.removeProperty('display')
        resultEl.innerHTML = `
          <div class="alert alert-danger mt-3">
            <i class="ri-error-warning-line me-1"></i>
            ${escapeHtml(err instanceof Error ? err.message : 'Import failed.')}
          </div>`
      }
    } finally {
      setButtonLoading(importBtn, false)
    }
  })

  // --- Local helper ---

  function showImportStatus(message: string, type: 'success' | 'danger' | 'warning' | 'info'): void {
    if (!resultEl) return
    resultEl.innerHTML = `<div class="alert alert-${type} mt-3">${message}</div>`
  }
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
