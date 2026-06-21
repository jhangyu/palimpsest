/**
 * S2-05: User AI Service — Playwright Tests
 * Spec: docs/test-specs/s2-05-user-ai-service.md
 *
 * Covers: AI Provider CRUD, Scan Models, Enable/Disable Toggle,
 * Reorder, Test Connection, Reveal API Key, Environment Fallback,
 * KEK Lifecycle, and Page Re-initialization Guard.
 *
 * Tests requiring authentication are marked test.skip until session fixture lands.
 * Run: npx playwright test tests/stage2/ai-service.spec.ts
 */
import { test, expect } from '@playwright/test'

// =============================================================================
// Page Load & Provider List
// =============================================================================
test.describe('Page Load & Provider List', () => {

  test.skip('5.01 Page load — shows spinner then renders provider list', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await expect(page.locator('.spinner-border')).toBeVisible()
    await expect(page.locator('#ai-providers-list')).toBeVisible()
  })

  test.skip('5.02 Page load — Runtime Status displays active chain', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await expect(page.locator('#ai-runtime-status')).toBeVisible()
  })

  test.skip('5.03 Page load — no providers shows empty state', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await expect(page.locator('#ai-providers-empty')).toBeVisible()
    await expect(page.locator('#ai-providers-empty')).toContainText('No AI providers configured')
  })

  test.skip('5.04 Provider list — masked API key does not expose plaintext', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    const list = page.locator('#ai-providers-list')
    await expect(list).toBeVisible()
    // DOM should only contain masked value, never full key
    const html = await list.innerHTML()
    expect(html).not.toMatch(/sk-[A-Za-z0-9]{20,}/)
  })

})

// =============================================================================
// Add Provider — Modal & Validation
// =============================================================================
test.describe('Add Provider — Modal & Validation', () => {

  test.skip('5.05 Add Provider — opens modal', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('#ai-add-provider-btn').click()
    const modal = page.locator('#ai-provider-form-modal')
    await expect(modal).toBeVisible()
    await expect(modal).toContainText('Add AI Provider')
    await expect(page.locator('#prov-label')).toHaveValue('')
  })

  test.skip('5.06 Add Provider — required field validation', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('#ai-add-provider-btn').click()
    await page.locator('#prov-modal-submit').click()
    await expect(page.locator('#prov-modal-alert')).toBeVisible()
    await expect(page.locator('#prov-modal-alert')).toContainText('Label, Protocol, Base URL, and Model are required')
  })

  test.skip('5.07 Add Provider — API Key required validation', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('#ai-add-provider-btn').click()
    await page.locator('#prov-label').fill('Test Provider')
    await page.locator('#prov-protocol').selectOption('openai')
    await page.locator('#prov-base-url').fill('https://api.openai.com/v1')
    await page.locator('#prov-model').fill('gpt-4')
    await page.locator('#prov-modal-submit').click()
    await expect(page.locator('#prov-modal-alert')).toContainText('API Key is required.')
  })

  test.skip('5.08 Add Provider — success saves and clears API key field', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('#ai-add-provider-btn').click()
    await page.locator('#prov-label').fill('My Provider')
    await page.locator('#prov-protocol').selectOption('openai')
    await page.locator('#prov-base-url').fill('https://api.openai.com/v1')
    await page.locator('#prov-api-key').fill('sk-test-key-12345')
    await page.locator('#prov-model').fill('gpt-4')
    await page.locator('#prov-modal-submit').click()
    // Modal closes, toast appears, table updated
    await expect(page.locator('#ai-provider-form-modal')).not.toBeVisible()
    await expect(page.locator('.toast')).toContainText('Provider added successfully.')
    await expect(page.locator('#ai-providers-list')).toContainText('My Provider')
    // API key field cleared
    await expect(page.locator('#prov-api-key')).toHaveValue('')
  })

  test.skip('5.09 Add Provider — duplicate label conflict', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('#ai-add-provider-btn').click()
    await page.locator('#prov-label').fill('Existing Provider')
    await page.locator('#prov-protocol').selectOption('openai')
    await page.locator('#prov-base-url').fill('https://api.openai.com/v1')
    await page.locator('#prov-api-key').fill('sk-test-key-12345')
    await page.locator('#prov-model').fill('gpt-4')
    await page.locator('#prov-modal-submit').click()
    await expect(page.locator('#prov-modal-alert')).toContainText('A provider with this label already exists.')
  })

  test.skip('5.10 Add Provider — API Key visibility toggle', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('#ai-add-provider-btn').click()
    await page.locator('#prov-api-key').fill('sk-secret')
    // Initially password type
    await expect(page.locator('#prov-api-key')).toHaveAttribute('type', 'password')
    // Toggle to text
    await page.locator('#prov-api-key-toggle').click()
    await expect(page.locator('#prov-api-key')).toHaveAttribute('type', 'text')
    await expect(page.locator('#prov-api-key-toggle i')).toHaveClass(/ri-eye-off-line/)
    // Toggle back to password
    await page.locator('#prov-api-key-toggle').click()
    await expect(page.locator('#prov-api-key')).toHaveAttribute('type', 'password')
  })

})

// =============================================================================
// Add Provider — Scan Models
// =============================================================================
test.describe('Add Provider — Scan Models', () => {

  test.skip('5.11 Scan Models — success shows model count and dropdown', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('#ai-add-provider-btn').click()
    await page.locator('#prov-protocol').selectOption('openai')
    await page.locator('#prov-base-url').fill('https://api.openai.com/v1')
    await page.locator('#prov-scan-models-btn').click()
    await expect(page.locator('#prov-scan-status')).toContainText('model(s) found')
    await expect(page.locator('#prov-model-select-wrapper')).toBeVisible()
  })

  test.skip('5.12 Scan Models — selecting model populates model input', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('#ai-add-provider-btn').click()
    await page.locator('#prov-protocol').selectOption('openai')
    await page.locator('#prov-base-url').fill('https://api.openai.com/v1')
    await page.locator('#prov-scan-models-btn').click()
    await expect(page.locator('#prov-model-select')).toBeVisible()
    await page.locator('#prov-model-select').selectOption({ index: 1 })
    const selectedValue = await page.locator('#prov-model-select').inputValue()
    await expect(page.locator('#prov-model')).toHaveValue(selectedValue)
  })

  test.skip('5.13 Scan Models — failure shows error', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('#ai-add-provider-btn').click()
    await page.locator('#prov-protocol').selectOption('openai')
    await page.locator('#prov-base-url').fill('https://invalid-url.example.com')
    await page.locator('#prov-scan-models-btn').click()
    await expect(page.locator('#prov-scan-status')).toHaveClass(/text-danger/)
  })

})

// =============================================================================
// Edit Provider
// =============================================================================
test.describe('Edit Provider', () => {

  test.skip('5.14 Edit Provider — opens modal with existing values', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    const editBtn = page.locator('[data-ai-action="edit"]').first()
    await editBtn.click()
    const modal = page.locator('#ai-provider-form-modal')
    await expect(modal).toBeVisible()
    await expect(page.locator('#providerModal .modal-title')).toContainText(/./)
    // Fields should be pre-populated
    await expect(page.locator('#prov-label')).not.toHaveValue('')
    await expect(page.locator('#prov-protocol')).not.toHaveValue('')
    await expect(page.locator('#prov-base-url')).not.toHaveValue('')
    await expect(page.locator('#prov-model')).not.toHaveValue('')
  })

  test.skip('5.15 Edit Provider — Update Key checkbox reveals key input', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="edit"]').first().click()
    // Key wrapper hidden by default in edit mode
    await expect(page.locator('#prov-api-key-wrapper')).toHaveClass(/d-none/)
    // Check the update key checkbox
    await page.locator('#prov-update-key-check').check()
    await expect(page.locator('#prov-api-key-wrapper')).not.toHaveClass(/d-none/)
    // Uncheck hides and clears
    await page.locator('#prov-update-key-check').uncheck()
    await expect(page.locator('#prov-api-key-wrapper')).toHaveClass(/d-none/)
    await expect(page.locator('#prov-api-key')).toHaveValue('')
  })

  test.skip('5.16 Edit Provider — successful update', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="edit"]').first().click()
    await page.locator('#prov-label').fill('Updated Provider Name')
    await page.locator('#prov-modal-submit').click()
    await expect(page.locator('#ai-provider-form-modal')).not.toBeVisible()
    await expect(page.locator('.toast')).toContainText('Provider updated successfully.')
    await expect(page.locator('#ai-providers-list')).toContainText('Updated Provider Name')
  })

  test.skip('5.17 Edit Provider — update with new API Key', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="edit"]').first().click()
    await page.locator('#prov-update-key-check').check()
    await page.locator('#prov-api-key').fill('sk-new-key-67890')
    await page.locator('#prov-modal-submit').click()
    await expect(page.locator('#ai-provider-form-modal')).not.toBeVisible()
    // API key field cleared after submit
    await expect(page.locator('#prov-api-key')).toHaveValue('')
  })

  test.skip('5.18 Edit Provider — revision conflict', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="edit"]').first().click()
    // Simulate external change causing revision conflict on submit
    await page.locator('#prov-label').fill('Conflict Test')
    await page.locator('#prov-modal-submit').click()
    await expect(page.locator('#prov-modal-alert')).toContainText('Provider settings have changed. Please close and reload.')
  })

})

// =============================================================================
// Delete Provider
// =============================================================================
test.describe('Delete Provider', () => {

  test.skip('5.19 Delete Provider — confirm removes from list', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    const providerRow = page.locator('[data-provider-row]').first()
    const providerText = await providerRow.textContent()
    // Mock window.confirm to return true
    page.on('dialog', dialog => dialog.accept())
    await page.locator('[data-ai-action="delete"]').first().click()
    await expect(page.locator('.toast')).toContainText('Provider deleted.')
    // Row should be removed
    await expect(page.locator('#ai-providers-list')).not.toContainText(providerText!)
  })

  test.skip('5.20 Delete Provider — cancel does not delete', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    const countBefore = await page.locator('[data-provider-row]').count()
    // Mock window.confirm to return false
    page.on('dialog', dialog => dialog.dismiss())
    await page.locator('[data-ai-action="delete"]').first().click()
    const countAfter = await page.locator('[data-provider-row]').count()
    expect(countAfter).toBe(countBefore)
  })

})

// =============================================================================
// Enable/Disable Toggle
// =============================================================================
test.describe('Enable/Disable Toggle', () => {

  test.skip('5.21 Toggle — enable a disabled provider', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    const toggle = page.locator('[data-ai-action="toggle-enabled"]').first()
    // Ensure it's unchecked (disabled) then check it
    if (await toggle.isChecked()) {
      await toggle.uncheck()
      await page.waitForTimeout(500)
    }
    await toggle.check()
    await expect(page.locator('.toast')).toContainText('enabled.')
    await expect(toggle).toBeChecked()
  })

  test.skip('5.22 Toggle — disable an enabled provider', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    const toggle = page.locator('[data-ai-action="toggle-enabled"]').first()
    // Ensure it's checked (enabled) then uncheck it
    if (!(await toggle.isChecked())) {
      await toggle.check()
      await page.waitForTimeout(500)
    }
    await toggle.uncheck()
    await expect(page.locator('.toast')).toContainText('disabled.')
    await expect(toggle).not.toBeChecked()
    // Runtime status should update
    await expect(page.locator('#ai-runtime-status')).toBeVisible()
  })

  test.skip('5.23 Toggle — API failure reverts checkbox', async ({ page }) => {
    // TODO: requires auth session fixture + mock API 500
    await page.goto('/users/ai-service')
    const toggle = page.locator('[data-ai-action="toggle-enabled"]').first()
    const initialState = await toggle.isChecked()
    // Simulate toggle (API will fail with mocked 500)
    if (initialState) {
      await toggle.uncheck()
    } else {
      await toggle.check()
    }
    await expect(page.locator('.toast.bg-danger, .toast-body')).toBeVisible()
    // Should revert to original state
    if (initialState) {
      await expect(toggle).toBeChecked()
    } else {
      await expect(toggle).not.toBeChecked()
    }
  })

})

// =============================================================================
// Provider Reorder
// =============================================================================
test.describe('Provider Reorder', () => {

  test.skip('5.24 Reorder — Move Up swaps provider to previous position', async ({ page }) => {
    // TODO: requires auth session fixture + at least 2 providers
    await page.goto('/users/ai-service')
    const rows = page.locator('[data-provider-row]')
    const secondRowId = await rows.nth(1).getAttribute('data-provider-row')
    await page.locator(`[data-ai-action="move-up"][data-provider-id="${secondRowId}"]`).click()
    // Second provider should now be first
    const firstRowIdAfter = await rows.nth(0).getAttribute('data-provider-row')
    expect(firstRowIdAfter).toBe(secondRowId)
  })

  test.skip('5.25 Reorder — Move Down swaps provider to next position', async ({ page }) => {
    // TODO: requires auth session fixture + at least 2 providers
    await page.goto('/users/ai-service')
    const rows = page.locator('[data-provider-row]')
    const firstRowId = await rows.nth(0).getAttribute('data-provider-row')
    await page.locator(`[data-ai-action="move-down"][data-provider-id="${firstRowId}"]`).click()
    // First provider should now be second
    const secondRowIdAfter = await rows.nth(1).getAttribute('data-provider-row')
    expect(secondRowIdAfter).toBe(firstRowId)
  })

  test.skip('5.26 Reorder — first provider Move Up button is disabled', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    const rows = page.locator('[data-provider-row]')
    const firstRowId = await rows.nth(0).getAttribute('data-provider-row')
    const moveUpBtn = page.locator(`[data-ai-action="move-up"][data-provider-id="${firstRowId}"]`)
    await expect(moveUpBtn).toHaveAttribute('disabled', '')
  })

  test.skip('5.27 Reorder — last provider Move Down button is disabled', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    const rows = page.locator('[data-provider-row]')
    const lastRowId = await rows.last().getAttribute('data-provider-row')
    const moveDownBtn = page.locator(`[data-ai-action="move-down"][data-provider-id="${lastRowId}"]`)
    await expect(moveDownBtn).toHaveAttribute('disabled', '')
  })

})

// =============================================================================
// Test Connection
// =============================================================================
test.describe('Test Connection', () => {

  test.skip('5.28 Test Connection — opens modal and auto-executes', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="test"]').first().click()
    const modal = page.locator('#ai-provider-test-modal')
    await expect(modal).toBeVisible()
    await expect(page.locator('#prov-test-modal-loading')).toBeVisible()
  })

  test.skip('5.29 Test Connection — success shows success alert', async ({ page }) => {
    // TODO: requires auth session fixture + mock test API returns health_status: "ok"
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="test"]').first().click()
    await expect(page.locator('#prov-test-modal-result')).toBeVisible()
    await expect(page.locator('#prov-test-modal-result')).toHaveClass(/alert-success/)
    await expect(page.locator('#prov-test-modal-result')).toContainText('Connection Successful')
  })

  test.skip('5.30 Test Connection — failure shows failure alert', async ({ page }) => {
    // TODO: requires auth session fixture + mock test API returns health_status != "ok"
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="test"]').first().click()
    await expect(page.locator('#prov-test-modal-result')).toBeVisible()
    await expect(page.locator('#prov-test-modal-result')).toHaveClass(/alert-danger/)
    await expect(page.locator('#prov-test-modal-result')).toContainText('Connection Failed')
    await expect(page.locator('#prov-test-result')).toContainText(/failure/i)
  })

  test.skip('5.31 Test Connection in Edit Modal — success', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="edit"]').first().click()
    await page.locator('#prov-test-btn').click()
    await expect(page.locator('#prov-test-result')).toBeVisible()
    await expect(page.locator('#prov-test-result')).toHaveClass(/alert-success/)
    await expect(page.locator('#prov-test-result')).toContainText('Connection successful')
  })

  test.skip('5.32 Test Connection in Edit Modal — failure', async ({ page }) => {
    // TODO: requires auth session fixture + mock test API failure
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="edit"]').first().click()
    await page.locator('#prov-test-btn').click()
    await expect(page.locator('#prov-test-result')).toBeVisible()
    await expect(page.locator('#prov-test-result')).toHaveClass(/alert-danger/)
    await expect(page.locator('#prov-test-result')).toContainText(/reason/i)
  })

})

// =============================================================================
// Reveal API Key
// =============================================================================
test.describe('Reveal API Key', () => {

  test.skip('5.33 Reveal — opens modal requiring password', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="reveal"]').first().click()
    const modal = page.locator('#ai-provider-reveal-modal')
    await expect(modal).toBeVisible()
    await expect(page.locator('#prov-reveal-password-section')).toBeVisible()
    await expect(page.locator('#prov-reveal-result')).toHaveClass(/d-none/)
  })

  test.skip('5.34 Reveal — empty password validation', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="reveal"]').first().click()
    await page.locator('#prov-reveal-submit').click()
    await expect(page.locator('#prov-reveal-alert')).toBeVisible()
    await expect(page.locator('#prov-reveal-alert')).toContainText('Current password is required.')
  })

  test.skip('5.35 Reveal — correct password shows plaintext key', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="reveal"]').first().click()
    await page.locator('#prov-reveal-password').fill('correct-password')
    await page.locator('#prov-reveal-submit').click()
    // Password section hidden, value shown
    await expect(page.locator('#prov-reveal-password-section')).not.toBeVisible()
    await expect(page.locator('#prov-reveal-value')).toBeVisible()
    await expect(page.locator('#prov-reveal-value')).not.toHaveValue('')
  })

  test.skip('5.36 Reveal — password field cleared after successful reveal', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="reveal"]').first().click()
    await page.locator('#prov-reveal-password').fill('correct-password')
    await page.locator('#prov-reveal-submit').click()
    await expect(page.locator('#prov-reveal-value')).toBeVisible()
    // Password input should be cleared immediately
    await expect(page.locator('#prov-reveal-password')).toHaveValue('')
  })

  test.skip('5.37 Reveal — closing modal clears plaintext value', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="reveal"]').first().click()
    await page.locator('#prov-reveal-password').fill('correct-password')
    await page.locator('#prov-reveal-submit').click()
    await expect(page.locator('#prov-reveal-value')).toBeVisible()
    // Close modal
    await page.locator('#ai-provider-reveal-modal .btn-close').click()
    await expect(page.locator('#ai-provider-reveal-modal')).not.toBeVisible()
    // Re-open to verify value is cleared
    await page.locator('[data-ai-action="reveal"]').first().click()
    await expect(page.locator('#prov-reveal-value')).toHaveValue('')
  })

  test.skip('5.38 Reveal — wrong password shows error', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="reveal"]').first().click()
    await page.locator('#prov-reveal-password').fill('wrong-password')
    await page.locator('#prov-reveal-submit').click()
    await expect(page.locator('#prov-reveal-alert')).toBeVisible()
    // Result section should remain hidden
    await expect(page.locator('#prov-reveal-result')).toHaveClass(/d-none/)
  })

  test.skip('5.39 Reveal — Copy button copies to clipboard', async ({ page }) => {
    // TODO: requires auth session fixture
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="reveal"]').first().click()
    await page.locator('#prov-reveal-password').fill('correct-password')
    await page.locator('#prov-reveal-submit').click()
    await expect(page.locator('#prov-reveal-copy')).toBeVisible()
    await page.locator('#prov-reveal-copy').click()
    // Icon should briefly change to check mark
    await expect(page.locator('#prov-reveal-copy .ri-check-line')).toBeVisible()
  })

})

// =============================================================================
// Environment Fallback
// =============================================================================
test.describe('Environment Fallback', () => {

  test.skip('5.40 Environment Fallback — shows active fallback info', async ({ page }) => {
    // TODO: requires auth session fixture + runtime-status returns environment_fallback.enabled: true
    await page.goto('/users/ai-service')
    const fallback = page.locator('#ai-env-fallback-status')
    await expect(fallback).toBeVisible()
    await expect(fallback).toHaveClass(/alert-info/)
    await expect(fallback).toContainText('Environment fallback active')
    await expect(page.locator('#ai-providers-list')).toContainText(/Environment fallback active/)
  })

  test.skip('5.41 Environment Fallback — no config shows notice', async ({ page }) => {
    // TODO: requires auth session fixture + runtime-status returns environment_fallback: null
    await page.goto('/users/ai-service')
    const fallback = page.locator('#ai-env-fallback-status')
    await expect(fallback).toBeVisible()
    await expect(fallback).toContainText('No environment fallback configured.')
  })

})

// =============================================================================
// KEK Lifecycle
// =============================================================================
test.describe('KEK Lifecycle', () => {

  test.skip('5.42 KEK — Reveal works after first KEK setup', async ({ page }) => {
    // TODO: requires auth session fixture + first-time KEK generation
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="reveal"]').first().click()
    await page.locator('#prov-reveal-password').fill('correct-password')
    await page.locator('#prov-reveal-submit').click()
    await expect(page.locator('#prov-reveal-value')).toBeVisible()
    await expect(page.locator('#prov-reveal-value')).not.toHaveValue('')
  })

  test.skip('5.43 KEK — Reveal works after password change (re-encrypt)', async ({ page }) => {
    // TODO: requires auth session fixture + password change scenario
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="reveal"]').first().click()
    await page.locator('#prov-reveal-password').fill('new-password')
    await page.locator('#prov-reveal-submit').click()
    await expect(page.locator('#prov-reveal-value')).toBeVisible()
    await expect(page.locator('#prov-reveal-value')).not.toHaveValue('')
  })

  test.skip('5.44 KEK — password reset shows needs-reentry state', async ({ page }) => {
    // TODO: requires auth session fixture + admin password reset scenario
    await page.goto('/users/ai-service')
    const providerRow = page.locator('[data-provider-row]').first()
    await expect(providerRow).toContainText('needs re-entry')
  })

})

// =============================================================================
// Page Re-initialization Guard
// =============================================================================
test.describe('Page Re-initialization Guard', () => {

  test.skip('5.45 Page revisit — avoids duplicate initialization', async ({ page }) => {
    // TODO: requires auth session fixture
    let apiCallCount = 0
    await page.route('**/ai/providers', (route) => { apiCallCount++; route.continue() })
    await page.goto('/users/ai-service')
    await expect(page.locator('#ai-providers-list')).toBeVisible()
    // Navigate away and back (SPA navigation)
    await page.goto('/dashboard')
    await page.goto('/users/ai-service')
    // data-inited guard should prevent duplicate event binding
    await expect(page.locator('#ai-providers-list')).toHaveAttribute('data-inited', 'true')
    expect(apiCallCount).toBe(1)
  })

})
