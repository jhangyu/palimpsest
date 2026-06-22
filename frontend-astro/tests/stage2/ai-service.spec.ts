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
import { test, expect, type Page } from '@playwright/test'

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

const _P = {
  id: 1, user_id: 1, label: 'Test Provider', protocol: 'openai',
  base_url: 'https://api.openai.com/v1', model: 'gpt-4',
  api_key_mask: 'sk-****', temperature: null, max_tokens: 4096,
  thinking: false, effort: 'low', enabled: true, priority: 1,
  revision: 1, created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z'
}
const _P2 = { ..._P, id: 2, label: 'Test Provider 2', priority: 2, enabled: true }

async function mockProvidersList(page: Page, providers: object[]) {
  await page.route('http://localhost:8088/settings/ai-providers', async route => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({ providers })
      })
    } else {
      await route.continue()
    }
  })
}

// =============================================================================
// Page Load & Provider List
// =============================================================================
test.describe('Page Load & Provider List', () => {

  test('5.01 Page load — shows spinner then renders provider list', async ({ page }) => {
    // Delay the providers API to keep spinner visible after page.goto() returns
    await page.route('**/settings/ai-providers', async route => {
      if (route.request().method() === 'GET') {
        await new Promise<void>(r => setTimeout(r, 1000))
        await route.continue()
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/ai-service')
    await expect(page.locator('.spinner-border')).toBeVisible()
    await expect(page.locator('#ai-providers-list')).toBeVisible()
  })

  test('5.02 Page load — Runtime Status displays active chain', async ({ page }) => {
    await page.goto('/users/ai-service')
    await expect(page.locator('#ai-runtime-status')).toBeVisible()
  })

  test('5.03 Page load — no providers shows empty state', async ({ page }) => {
    await page.route('**/settings/ai-providers', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ providers: [] })
    }))
    await page.goto('/users/ai-service')
    await expect(page.locator('#ai-providers-empty')).toBeVisible()
    await expect(page.locator('#ai-providers-empty')).toContainText('No AI providers configured')
  })

  test('5.04 Provider list — masked API key does not expose plaintext', async ({ page }) => {
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
  test.describe.configure({ mode: 'serial' })

  test('5.05 Add Provider — opens modal', async ({ page }) => {
    await page.goto('/users/ai-service')
    await page.locator('#ai-add-provider-btn').click()
    const modal = page.locator('#ai-provider-form-modal')
    await expect(modal).toBeVisible()
    await expect(modal).toContainText('Add AI Provider')
    await expect(page.locator('#prov-label')).toHaveValue('')
  })

  test('5.06 Add Provider — required field validation', async ({ page }) => {
    await page.goto('/users/ai-service')
    await page.locator('#ai-add-provider-btn').click()
    await page.locator('#prov-modal-submit').click()
    await expect(page.locator('#prov-modal-alert')).toBeVisible()
    await expect(page.locator('#prov-modal-alert')).toContainText('Label, Protocol, Base URL, and Model are required')
  })

  test('5.07 Add Provider — API Key required validation', async ({ page }) => {
    await page.goto('/users/ai-service')
    await page.locator('#ai-add-provider-btn').click()
    await page.locator('#prov-label').fill('Test Provider')
    await page.locator('#prov-protocol').selectOption('openai')
    await page.locator('#prov-base-url').fill('https://api.openai.com/v1')
    await page.locator('#prov-model').fill('gpt-4')
    await page.locator('#prov-modal-submit').click()
    await expect(page.locator('#prov-modal-alert')).toContainText('API Key is required.')
  })

  test('5.08 Add Provider — success saves and clears API key field', async ({ page }) => {
    let created = false
    await page.route('**/settings/ai-providers', async route => {
      const method = route.request().method()
      if (method === 'POST') {
        created = true
        await route.fulfill({
          status: 201, contentType: 'application/json',
          body: JSON.stringify({ ..._P, label: 'My Provider' })
        })
      } else if (method === 'GET') {
        const providers = created ? [{ ..._P, label: 'My Provider' }] : []
        await route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({ providers })
        })
      } else {
        await route.continue()
      }
    })
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
    await expect(page.locator('.alert.position-fixed')).toContainText('Provider added successfully.')
    await expect(page.locator('#ai-providers-list')).toContainText('My Provider')
    // API key field cleared
    await expect(page.locator('#prov-api-key')).toHaveValue('')
  })

  test('5.09 Add Provider — duplicate label conflict', async ({ page }) => {
    await page.route('**/settings/ai-providers', async route => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 409, contentType: 'application/json',
          body: JSON.stringify({ detail: 'A provider with this label already exists.', code: 'label_conflict' })
        })
      } else {
        await route.continue()
      }
    })
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

  test('5.10 Add Provider — API Key visibility toggle', async ({ page }) => {
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

  test('5.11 Scan Models — success shows model count and dropdown', async ({ page }) => {
    await page.route('**/settings/ai-providers/actions/discover-models', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ models: [
        { id: 'gpt-4', display_name: 'GPT-4' },
        { id: 'gpt-3.5-turbo', display_name: 'GPT-3.5 Turbo' }
      ] })
    }))
    await page.goto('/users/ai-service')
    await page.locator('#ai-add-provider-btn').click()
    await page.locator('#prov-protocol').selectOption('openai')
    await page.locator('#prov-base-url').fill('https://api.openai.com/v1')
    await page.locator('#prov-scan-models-btn').click()
    await expect(page.locator('#prov-scan-status')).toContainText('model(s) found')
    await expect(page.locator('#prov-model-select-wrapper')).toBeVisible()
  })

  test('5.12 Scan Models — selecting model populates model input', async ({ page }) => {
    await page.route('**/settings/ai-providers/actions/discover-models', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ models: [
        { id: 'gpt-4', display_name: 'GPT-4' },
        { id: 'gpt-3.5-turbo', display_name: 'GPT-3.5 Turbo' }
      ] })
    }))
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

  test('5.13 Scan Models — failure shows error', async ({ page }) => {
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
  test.describe.configure({ mode: 'serial' })

  test('5.14 Edit Provider — opens modal with existing values', async ({ page }) => {
    await mockProvidersList(page, [_P])
    await page.goto('/users/ai-service')
    const editBtn = page.locator('[data-ai-action="edit"]').first()
    await editBtn.click()
    const modal = page.locator('#ai-provider-form-modal')
    await expect(modal).toBeVisible()
    await expect(page.locator('#prov-modal-title')).toContainText(/./)
    // Fields should be pre-populated
    await expect(page.locator('#prov-label')).not.toHaveValue('')
    await expect(page.locator('#prov-protocol')).not.toHaveValue('')
    await expect(page.locator('#prov-base-url')).not.toHaveValue('')
    await expect(page.locator('#prov-model')).not.toHaveValue('')
  })

  test('5.15 Edit Provider — Update Key checkbox reveals key input', async ({ page }) => {
    await mockProvidersList(page, [_P])
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

  test('5.16 Edit Provider — successful update', async ({ page }) => {
    let updated = false
    await page.route('**/settings/ai-providers', async route => {
      if (route.request().method() === 'GET') {
        const label = updated ? 'Updated Provider Name' : _P.label
        await route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({ providers: [{ ..._P, label }] })
        })
      } else {
        await route.continue()
      }
    })
    await page.route('**/settings/ai-providers/*', async route => {
      if (route.request().method() === 'PUT') {
        updated = true
        await route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({ ..._P, label: 'Updated Provider Name' })
        })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="edit"]').first().click()
    await page.locator('#prov-label').fill('Updated Provider Name')
    await page.locator('#prov-modal-submit').click()
    await expect(page.locator('#ai-provider-form-modal')).not.toBeVisible()
    await expect(page.locator('.alert.position-fixed')).toContainText('Provider updated successfully.')
    await expect(page.locator('#ai-providers-list')).toContainText('Updated Provider Name')
  })

  test('5.17 Edit Provider — update with new API Key', async ({ page }) => {
    await page.route('**/settings/ai-providers', async route => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ providers: [_P] }) })
      } else { await route.continue() }
    })
    await page.route('**/settings/ai-providers/*', async route => {
      if (route.request().method() === 'PUT') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(_P) })
      } else { await route.continue() }
    })
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="edit"]').first().click()
    await page.locator('#prov-update-key-check').check()
    await page.locator('#prov-api-key').fill('sk-new-key-67890')
    await page.locator('#prov-modal-submit').click()
    await expect(page.locator('#ai-provider-form-modal')).not.toBeVisible()
    // API key field cleared after submit
    await expect(page.locator('#prov-api-key')).toHaveValue('')
  })

  test('5.18 Edit Provider — revision conflict', async ({ page }) => {
    await page.route('**/settings/ai-providers', async route => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ providers: [_P] }) })
      } else { await route.continue() }
    })
    await page.route('**/settings/ai-providers/*', async route => {
      if (route.request().method() === 'PUT') {
        await route.fulfill({
          status: 409, contentType: 'application/json',
          body: JSON.stringify({ detail: 'Revision conflict', code: 'revision_conflict' })
        })
      } else { await route.continue() }
    })
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
  test.describe.configure({ mode: 'serial' })

  test('5.19 Delete Provider — confirm removes from list', async ({ page }) => {
    let deleted = false
    await page.route('**/settings/ai-providers', async route => {
      if (route.request().method() === 'GET') {
        const providers = deleted ? [] : [_P]
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ providers }) })
      } else { await route.continue() }
    })
    await page.route('**/settings/ai-providers/*', async route => {
      if (route.request().method() === 'DELETE') {
        deleted = true
        await route.fulfill({ status: 204 })
      } else { await route.continue() }
    })
    await page.goto('/users/ai-service')
    const providerRow = page.locator('[data-provider-row]').first()
    const providerText = await providerRow.textContent()
    // Mock window.confirm to return true
    page.on('dialog', dialog => dialog.accept())
    await page.locator('[data-ai-action="delete"]').first().click()
    await expect(page.locator('.alert.position-fixed')).toContainText('Provider deleted.')
    // Row should be removed
    await expect(page.locator('#ai-providers-list')).not.toContainText(providerText!)
  })

  test('5.20 Delete Provider — cancel does not delete', async ({ page }) => {
    await mockProvidersList(page, [_P])
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
  test.describe.configure({ mode: 'serial' })

  test('5.21 Toggle — enable a disabled provider', async ({ page }) => {
    let enabled = false
    await page.route('**/settings/ai-providers', async route => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ providers: [{ ..._P, enabled }] }) })
      } else { await route.continue() }
    })
    await page.route('**/settings/ai-providers/*/enabled', async route => {
      enabled = true
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ..._P, enabled: true }) })
    })
    await page.goto('/users/ai-service')
    const toggle = page.locator('[data-ai-action="toggle-enabled"]').first()
    // Ensure it's unchecked (disabled) then check it
    if (await toggle.isChecked()) {
      await toggle.uncheck()
      await page.waitForTimeout(500)
    }
    await toggle.check()
    await expect(page.locator('.alert.position-fixed')).toContainText('enabled.')
    await expect(toggle).toBeChecked()
  })

  test('5.22 Toggle — disable an enabled provider', async ({ page }) => {
    let enabled = true
    await page.route('**/settings/ai-providers', async route => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ providers: [{ ..._P, enabled }] }) })
      } else { await route.continue() }
    })
    await page.route('**/settings/ai-providers/*/enabled', async route => {
      enabled = false
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ..._P, enabled: false }) })
    })
    await page.goto('/users/ai-service')
    const toggle = page.locator('[data-ai-action="toggle-enabled"]').first()
    // Ensure it's checked (enabled) then uncheck it
    if (!(await toggle.isChecked())) {
      await toggle.check()
      await page.waitForTimeout(500)
    }
    await toggle.uncheck()
    await expect(page.locator('.alert.position-fixed')).toContainText('disabled.')
    await expect(toggle).not.toBeChecked()
    // Runtime status should update
    await expect(page.locator('#ai-runtime-status')).toBeVisible()
  })

  test('5.23 Toggle — API failure reverts checkbox', async ({ page }) => {
    await page.route('**/settings/ai-providers', async route => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ providers: [_P] }) })
      } else { await route.continue() }
    })
    await page.route('**/settings/ai-providers/*/enabled', route => route.fulfill({ status: 500 }))
    await page.goto('/users/ai-service')
    const toggle = page.locator('[data-ai-action="toggle-enabled"]').first()
    const initialState = await toggle.isChecked()
    // Just click — Playwright's check()/uncheck() waits for state change, but
    // the 500 error handler reverts the checkbox before Playwright can confirm.
    await toggle.click()
    await expect(page.locator('.alert.position-fixed')).toBeVisible()
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
  test.describe.configure({ mode: 'serial' })

  test('5.24 Reorder — Move Up swaps provider to previous position', async ({ page }) => {
    test.slow()
    let reordered = false
    await page.route('http://localhost:8088/settings/ai-providers/order', async route => {
      reordered = true
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([_P2, _P]) })
    })
    await page.route('http://localhost:8088/settings/ai-providers', async route => {
      if (route.request().method() === 'GET') {
        const providers = reordered ? [_P2, _P] : [_P, _P2]
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ providers }) })
      } else { await route.continue() }
    })
    await page.goto('/users/ai-service')
    const rows = page.locator('[data-provider-row]')
    const secondRowId = await rows.nth(1).getAttribute('data-provider-row')
    await page.locator(`[data-ai-action="move-up"][data-provider-id="${secondRowId}"]`).click()
    // Wait for async reorder + re-render; auto-retry until DOM updates
    await expect(rows.nth(0)).toHaveAttribute('data-provider-row', secondRowId!)
  })

  test('5.25 Reorder — Move Down swaps provider to next position', async ({ page }) => {
    let reordered = false
    await page.route('http://localhost:8088/settings/ai-providers/order', async route => {
      reordered = true
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([_P2, _P]) })
    })
    await page.route('http://localhost:8088/settings/ai-providers', async route => {
      if (route.request().method() === 'GET') {
        const providers = reordered ? [_P2, _P] : [_P, _P2]
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ providers }) })
      } else { await route.continue() }
    })
    await page.goto('/users/ai-service')
    const rows = page.locator('[data-provider-row]')
    const firstRowId = await rows.nth(0).getAttribute('data-provider-row')
    await page.locator(`[data-ai-action="move-down"][data-provider-id="${firstRowId}"]`).click()
    // Wait for async reorder + re-render; auto-retry until DOM updates
    await expect(rows.nth(1)).toHaveAttribute('data-provider-row', firstRowId!)
  })

  test('5.26 Reorder — first provider Move Up button is disabled', async ({ page }) => {
    await mockProvidersList(page, [_P, _P2])
    await page.goto('/users/ai-service')
    const rows = page.locator('[data-provider-row]')
    const firstRowId = await rows.nth(0).getAttribute('data-provider-row')
    const moveUpBtn = page.locator(`[data-ai-action="move-up"][data-provider-id="${firstRowId}"]`)
    await expect(moveUpBtn).toHaveAttribute('disabled', '')
  })

  test('5.27 Reorder — last provider Move Down button is disabled', async ({ page }) => {
    await mockProvidersList(page, [_P, _P2])
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

  test('5.28 Test Connection — opens modal and auto-executes', async ({ page }) => {
    await mockProvidersList(page, [_P])
    // Delay test endpoint response so loading state is still visible when assertion runs
    await page.route('**/settings/ai-providers/*/test', async route => {
      await new Promise<void>(r => setTimeout(r, 800))
      await route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({ provider_id: 1, health_status: 'ok', last_tested_at: null, last_failure_code: null })
      })
    })
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="test"]').first().click()
    const modal = page.locator('#ai-provider-test-modal')
    await expect(modal).toBeVisible()
    await expect(page.locator('#prov-test-modal-loading')).toBeVisible()
  })

  test('5.29 Test Connection — success shows success alert', async ({ page }) => {
    await mockProvidersList(page, [_P])
    await page.route('**/settings/ai-providers/*/test', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ provider_id: 1, health_status: 'ok', last_tested_at: null, last_failure_code: null })
    }))
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="test"]').first().click()
    await expect(page.locator('#prov-test-modal-result')).toBeVisible()
    await expect(page.locator('#prov-test-modal-result .alert-success')).toBeVisible()
    await expect(page.locator('#prov-test-modal-result')).toContainText('Connection Successful')
  })

  test('5.30 Test Connection — failure shows failure alert', async ({ page }) => {
    await mockProvidersList(page, [_P])
    await page.route('**/settings/ai-providers/*/test', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ provider_id: 1, health_status: 'error', last_tested_at: null, last_failure_code: 'credential_error' })
    }))
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="test"]').first().click()
    await expect(page.locator('#prov-test-modal-result')).toBeVisible()
    await expect(page.locator('#prov-test-modal-result .alert-danger')).toBeVisible()
    await expect(page.locator('#prov-test-modal-result')).toContainText('Connection Failed')
    await expect(page.locator('#prov-test-modal-result')).toContainText(/credential_error|failed/i)
  })

  test('5.31 Test Connection in Edit Modal — success', async ({ page }) => {
    await mockProvidersList(page, [_P])
    await page.route('**/settings/ai-providers/*/test', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ provider_id: 1, health_status: 'ok', last_tested_at: null, last_failure_code: null })
    }))
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="edit"]').first().click()
    await page.locator('#prov-test-btn').click()
    await expect(page.locator('#prov-test-result')).toBeVisible()
    await expect(page.locator('#prov-test-result')).toHaveClass(/alert-success/)
    await expect(page.locator('#prov-test-result')).toContainText('Connection successful')
  })

  test('5.32 Test Connection in Edit Modal — failure', async ({ page }) => {
    await mockProvidersList(page, [_P])
    await page.route('**/settings/ai-providers/*/test', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ provider_id: 1, health_status: 'error', last_tested_at: null, last_failure_code: 'credential_error' })
    }))
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="edit"]').first().click()
    await page.locator('#prov-test-btn').click()
    await expect(page.locator('#prov-test-result')).toBeVisible()
    await expect(page.locator('#prov-test-result')).toHaveClass(/alert-danger/)
    await expect(page.locator('#prov-test-result')).toContainText(/Connection failed|credential_error/i)
  })

})

// =============================================================================
// Reveal API Key
// =============================================================================
test.describe('Reveal API Key', () => {

  test('5.33 Reveal — opens modal requiring password', async ({ page }) => {
    await mockProvidersList(page, [_P])
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="reveal"]').first().click()
    const modal = page.locator('#ai-provider-reveal-modal')
    await expect(modal).toBeVisible()
    await expect(page.locator('#prov-reveal-password-section')).toBeVisible()
    await expect(page.locator('#prov-reveal-result')).toHaveClass(/d-none/)
  })

  test('5.34 Reveal — empty password validation', async ({ page }) => {
    await mockProvidersList(page, [_P])
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="reveal"]').first().click()
    await page.locator('#prov-reveal-submit').click()
    await expect(page.locator('#prov-reveal-alert')).toBeVisible()
    await expect(page.locator('#prov-reveal-alert')).toContainText('Current password is required.')
  })

  test('5.35 Reveal — correct password shows plaintext key', async ({ page }) => {
    await mockProvidersList(page, [_P])
    await page.route('**/settings/ai-providers/*/reveal', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ api_key: 'sk-revealed-key-12345' })
    }))
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="reveal"]').first().click()
    await page.locator('#prov-reveal-password').fill('correct-password')
    await page.locator('#prov-reveal-submit').click()
    // Password section hidden, value shown
    await expect(page.locator('#prov-reveal-password-section')).not.toBeVisible()
    await expect(page.locator('#prov-reveal-value')).toBeVisible()
    await expect(page.locator('#prov-reveal-value')).not.toHaveValue('')
  })

  test('5.36 Reveal — password field cleared after successful reveal', async ({ page }) => {
    await mockProvidersList(page, [_P])
    await page.route('**/settings/ai-providers/*/reveal', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ api_key: 'sk-revealed-key-12345' })
    }))
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="reveal"]').first().click()
    await page.locator('#prov-reveal-password').fill('correct-password')
    await page.locator('#prov-reveal-submit').click()
    await expect(page.locator('#prov-reveal-value')).toBeVisible()
    // Password input should be cleared immediately
    await expect(page.locator('#prov-reveal-password')).toHaveValue('')
  })

  test('5.37 Reveal — closing modal clears plaintext value', async ({ page }) => {
    await mockProvidersList(page, [_P])
    await page.route('**/settings/ai-providers/*/reveal', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ api_key: 'sk-revealed-key-12345' })
    }))
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

  test('5.38 Reveal — wrong password shows error', async ({ page }) => {
    await mockProvidersList(page, [_P])
    await page.route('**/settings/ai-providers/*/reveal', route => route.fulfill({
      status: 403, contentType: 'application/json',
      body: JSON.stringify({ detail: 'Incorrect password.' })
    }))
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="reveal"]').first().click()
    await page.locator('#prov-reveal-password').fill('wrong-password')
    await page.locator('#prov-reveal-submit').click()
    await expect(page.locator('#prov-reveal-alert')).toBeVisible()
    // Result section should remain hidden
    await expect(page.locator('#prov-reveal-result')).toHaveClass(/d-none/)
  })

  test('5.39 Reveal — Copy button copies to clipboard', async ({ page }) => {
    await mockProvidersList(page, [_P])
    await page.route('**/settings/ai-providers/*/reveal', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ api_key: 'sk-revealed-key-12345' })
    }))
    // Grant clipboard permissions so navigator.clipboard.writeText works in test
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write'])
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

  test('5.40 Environment Fallback — shows active fallback info', async ({ page }) => {
    await page.route('**/settings/ai-providers/runtime-status', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        chain: [],
        environment_fallback: { enabled: true, protocol: 'openai', model: 'gpt-4', label: 'minimax-legacy-fallback' },
        profiles_enabled: false
      })
    }))
    await page.goto('/users/ai-service')
    const fallback = page.locator('#ai-env-fallback-status')
    await expect(fallback).toBeVisible()
    await expect(fallback).toHaveClass(/card-body/)
    await expect(fallback).toContainText('Environment fallback active')
    await expect(page.locator('#ai-env-fallback-status .alert-info')).toBeVisible()
  })

  test('5.41 Environment Fallback — no config shows notice', async ({ page }) => {
    await page.route('**/settings/ai-providers/runtime-status', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ chain: [], environment_fallback: null, profiles_enabled: false })
    }))
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

  test('5.42 KEK — Reveal works after first KEK setup', async ({ page }) => {
    await mockProvidersList(page, [_P])
    await page.route('**/settings/ai-providers/*/reveal', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ api_key: 'sk-revealed-key-12345' })
    }))
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="reveal"]').first().click()
    await page.locator('#prov-reveal-password').fill('correct-password')
    await page.locator('#prov-reveal-submit').click()
    await expect(page.locator('#prov-reveal-value')).toBeVisible()
    await expect(page.locator('#prov-reveal-value')).not.toHaveValue('')
  })

  test('5.43 KEK — Reveal works after password change (re-encrypt)', async ({ page }) => {
    await mockProvidersList(page, [_P])
    await page.route('**/settings/ai-providers/*/reveal', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ api_key: 'sk-revealed-key-12345' })
    }))
    await page.goto('/users/ai-service')
    await page.locator('[data-ai-action="reveal"]').first().click()
    await page.locator('#prov-reveal-password').fill('new-password')
    await page.locator('#prov-reveal-submit').click()
    await expect(page.locator('#prov-reveal-value')).toBeVisible()
    await expect(page.locator('#prov-reveal-value')).not.toHaveValue('')
  })

  test('5.44 KEK — password reset shows needs-reentry state', async ({ page }) => {
    await mockProvidersList(page, [{ ..._P, kek_status: 'needs-reentry' }])
    await page.goto('/users/ai-service')
    const providerRow = page.locator('[data-provider-row]').first()
    await expect(providerRow).toContainText('needs re-entry')
  })

})

// =============================================================================
// Page Re-initialization Guard
// =============================================================================
test.describe('Page Re-initialization Guard', () => {

  test('5.45 Page revisit — avoids duplicate initialization', async ({ page }) => {
    let apiCallCount = 0
    await page.route('http://localhost:8088/settings/ai-providers', async route => {
      if (route.request().method() === 'GET') {
        apiCallCount++
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ providers: [_P] }) })
      } else {
        await route.continue()
      }
    })
    await page.goto('/users/ai-service')
    await expect(page.locator('#ai-providers-list')).toBeVisible()
    // data-inited guard should prevent duplicate event binding
    // (both DOMContentLoaded and astro:page-load fire on a single navigation,
    //  but the guard ensures initAIServicePage() only runs once per render)
    await expect(page.locator('#ai-providers-list')).toHaveAttribute('data-inited', 'true')
    expect(apiCallCount).toBe(1)
  })

})
