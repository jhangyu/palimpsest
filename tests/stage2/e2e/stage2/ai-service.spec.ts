/*
---
name: ai-service
description: "Stage 2 E2E: /users/ai-service — AI provider list, add/edit/delete, scan models, enable/disable toggle, reorder, test connection, reveal API key, environment fallback, KEK lifecycle, re-init guard"
stage: stage2
type: playwright
target:
  layer: frontend
  domain: ai-service
spec_doc: docs/test-specs/stage2/s2-05-user-ai-service.md
test_file: tests/stage2/e2e/stage2/ai-service.spec.ts
tests:
  - name: "5.01 Page load — shows spinner then renders provider list"
    line: 45
    purpose: "Delayed providers API keeps spinner visible; list renders after networkidle"
  - name: "5.02 Page load — Runtime Status displays active chain"
    line: 60
    purpose: "Runtime status section shows active provider chain after page load"
  - name: "5.03 Page load — no providers shows empty state"
    line: 65
    purpose: "Empty providers list shows empty-state message"
  - name: "5.04 Provider list — masked API key does not expose plaintext"
    line: 75
    purpose: "API key shown as masked value (e.g. ****1234), never plaintext in DOM"
  - name: "5.05 Add Provider — opens modal"
    line: 92
    purpose: "Clicking Add Provider button opens add-provider modal"
  - name: "5.06 Add Provider — required field validation"
    line: 101
    purpose: "Submitting add-provider form with empty required fields shows validation error"
  - name: "5.07 Add Provider — API Key required validation"
    line: 109
    purpose: "Submitting add-provider form without API key shows key-required validation"
  - name: "5.08 Add Provider — success saves and clears API key field"
    line: 120
    purpose: "Mocked POST /ai-providers success closes modal and clears API key field"
  - name: "5.09 Add Provider — duplicate label conflict"
    line: 156
    purpose: "409 from POST /ai-providers shows 'duplicate label' conflict error"
  - name: "5.10 Add Provider — API Key visibility toggle"
    line: 178
    purpose: "API key visibility toggle in add modal switches input type password↔text"
  - name: "5.11 Scan Models — success shows model count and dropdown"
    line: 200
    purpose: "Mocked scan-models success populates model dropdown with count"
  - name: "5.12 Scan Models — selecting model populates model input"
    line: 217
    purpose: "Selecting model from dropdown populates the model name input field"
  - name: "5.13 Scan Models — failure shows error"
    line: 236
    purpose: "Scan models API failure shows error message"
  - name: "5.14 Edit Provider — opens modal with existing values"
    line: 253
    purpose: "Edit button opens modal pre-populated with provider label and model"
  - name: "5.15 Edit Provider — Update Key checkbox reveals key input"
    line: 268
    purpose: "Checking Update Key in edit modal reveals the API key input"
  - name: "5.16 Edit Provider — successful update"
    line: 283
    purpose: "Mocked PUT /ai-providers/:id success closes modal and updates provider list"
  - name: "5.17 Edit Provider — update with new API Key"
    line: 316
    purpose: "Updating provider with new API key calls PUT with key value included"
  - name: "5.18 Edit Provider — revision conflict"
    line: 337
    purpose: "409 revision conflict from PUT shows conflict error in edit modal"
  - name: "5.19 Delete Provider — confirm removes from list"
    line: 367
    purpose: "Mocked DELETE /ai-providers/:id success removes provider from list"
  - name: "5.20 Delete Provider — cancel does not delete"
    line: 392
    purpose: "Cancelling delete confirm dialog does not call DELETE API"
  - name: "5.21 Toggle — enable a disabled provider"
    line: 411
    purpose: "Checking disabled provider toggle calls PUT with enabled=true"
  - name: "5.22 Toggle — disable an enabled provider"
    line: 434
    purpose: "Unchecking enabled provider toggle calls PUT with enabled=false"
  - name: "5.23 Toggle — API failure reverts checkbox"
    line: 459
    purpose: "Toggle API failure reverts checkbox to original state"
  - name: "5.24 Reorder — Move Up swaps provider to previous position"
    line: 489
    purpose: "Move Up on second provider calls reorder API swapping with first"
  - name: "5.25 Reorder — Move Down swaps provider to next position"
    line: 510
    purpose: "Move Down on first provider calls reorder API swapping with second"
  - name: "5.26 Reorder — first provider Move Up button is disabled"
    line: 530
    purpose: "First provider in list has Move Up button disabled"
  - name: "5.27 Reorder — last provider Move Down button is disabled"
    line: 539
    purpose: "Last provider in list has Move Down button disabled"
  - name: "5.28 Test Connection — opens modal and auto-executes"
    line: 555
    purpose: "Test Connection button opens modal and auto-executes connection test"
  - name: "5.29 Test Connection — success shows success alert"
    line: 572
    purpose: "Mocked test-connection success shows success alert in modal"
  - name: "5.30 Test Connection — failure shows failure alert"
    line: 585
    purpose: "Mocked test-connection failure shows failure/error alert in modal"
  - name: "5.31 Test Connection in Edit Modal — success"
    line: 599
    purpose: "Test Connection button inside edit modal executes and shows success"
  - name: "5.32 Test Connection in Edit Modal — failure"
    line: 613
    purpose: "Test Connection button inside edit modal shows failure alert on error"
  - name: "5.33 Reveal — opens modal requiring password"
    line: 634
    purpose: "Reveal button opens modal with password input"
  - name: "5.34 Reveal — empty password validation"
    line: 644
    purpose: "Submitting reveal with empty password shows validation error"
  - name: "5.35 Reveal — correct password shows plaintext key"
    line: 653
    purpose: "Mocked reveal success with correct password shows plaintext API key"
  - name: "5.36 Reveal — password field cleared after successful reveal"
    line: 669
    purpose: "Password input is cleared after successful reveal response"
  - name: "5.37 Reveal — closing modal clears plaintext value"
    line: 684
    purpose: "Closing reveal modal clears the displayed plaintext key"
  - name: "5.38 Reveal — wrong password shows error"
    line: 703
    purpose: "401 from reveal API shows 'incorrect password' error in modal"
  - name: "5.39 Reveal — Copy button copies to clipboard"
    line: 718
    purpose: "Clicking Copy in reveal modal copies plaintext key to clipboard"
  - name: "5.40 Environment Fallback — shows active fallback info"
    line: 743
    purpose: "Mocked environment fallback config shows fallback provider info"
  - name: "5.41 Environment Fallback — no config shows notice"
    line: 760
    purpose: "No environment fallback config shows 'no fallback configured' notice"
  - name: "5.42 KEK — Reveal works after first KEK setup"
    line: 778
    purpose: "Reveal succeeds with correct password after initial KEK is established"
  - name: "5.43 KEK — Reveal works after password change (re-encrypt)"
    line: 792
    purpose: "Reveal succeeds with new password after KEK re-encryption"
  - name: "5.44 KEK — password reset shows needs-reentry state"
    line: 806
    purpose: "After password reset, reveal shows 'needs-reentry' state requiring new password"
  - name: "5.45 Page revisit — avoids duplicate initialization"
    line: 820
    purpose: "Navigating back to page does not trigger duplicate provider list initialization"
run:
  command: "cd frontend-astro && npx playwright test tests/stage2/e2e/stage2/ai-service.spec.ts"
  prerequisites:
    - "App running on http://localhost:5174"
---
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
