/* global fetch */
/**
 * ai-tokens.ts — Settings / Configuration / AI Tokens page handler
 *
 * Implements AI token CRUD, test, reveal, and set-default flows.
 * Uses direct fetch calls (credentials: "include", CSRF header) instead of
 * modifying api.ts — A4a (users.ts) is the secondary owner of that file.
 *
 * Security considerations:
 * - Plaintext tokens are NEVER stored in JS variables beyond the immediate
 *   render call that sets the readonly input value.
 * - Reveal modal clears the plaintext from the DOM immediately on close.
 * - No console.log of token values, prefixes, or ciphertext.
 * - All state-changing requests include the X-CSRF-Token header.
 */

import { escapeHtml, escapeAttr } from '@/scripts/utils'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const API_BASE = import.meta.env.DEV ? 'http://localhost:8088' : ''

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AIToken {
  id: number
  provider: string
  label: string
  token_mask: string
  token_last4: string | null
  is_default: boolean
  needs_reentry: boolean
  created_at: string
  updated_at: string
  last_used_at: string | null
}

// ---------------------------------------------------------------------------
// CSRF helper — local copy to avoid api.ts merge conflict
// ---------------------------------------------------------------------------

function getCsrfToken(): string {
  const match = document.cookie
    .split('; ')
    .find((row) => row.startsWith('csrf_token='))
  return match ? decodeURIComponent(match.split('=')[1]) : ''
}

function stateChangingHeaders(extra: Record<string, string> = {}): HeadersInit {
  const csrfToken = getCsrfToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...extra
  }
  if (csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }
  return headers
}

// ---------------------------------------------------------------------------
// Error helper
// ---------------------------------------------------------------------------

async function extractError(res: Response): Promise<string> {
  try {
    const body = await res.json()
    return body.detail || `HTTP ${res.status}`
  } catch {
    return `HTTP ${res.status}`
  }
}

async function throwOnError(res: Response): Promise<void> {
  if (!res.ok) {
    if (res.status === 401) {
      window.location.href = '/authentication/modern/login'
      throw new Error('Unauthorized')
    }
    throw new Error(await extractError(res))
  }
}

// ---------------------------------------------------------------------------
// Local API helpers
// ---------------------------------------------------------------------------

export async function listTokens(): Promise<AIToken[]> {
  const res = await fetch(`${API_BASE}/settings/ai-tokens`, {
    credentials: 'include'
  })
  await throwOnError(res)
  const data = await res.json()
  return Array.isArray(data) ? data : (data.tokens ?? [])
}

export async function createToken(
  provider: string,
  label: string,
  token: string,
  currentPassword: string
): Promise<AIToken> {
  const res = await fetch(`${API_BASE}/settings/ai-tokens`, {
    method: 'POST',
    headers: stateChangingHeaders(),
    credentials: 'include',
    body: JSON.stringify({ provider, label, token, current_password: currentPassword })
  })
  await throwOnError(res)
  return res.json()
}

export async function updateToken(
  tokenId: number,
  token: string,
  currentPassword: string
): Promise<AIToken> {
  const res = await fetch(`${API_BASE}/settings/ai-tokens/${tokenId}`, {
    method: 'PUT',
    headers: stateChangingHeaders(),
    credentials: 'include',
    body: JSON.stringify({ token, current_password: currentPassword })
  })
  await throwOnError(res)
  return res.json()
}

export async function deleteToken(tokenId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/settings/ai-tokens/${tokenId}`, {
    method: 'DELETE',
    headers: stateChangingHeaders(),
    credentials: 'include'
  })
  await throwOnError(res)
}

export async function testToken(
  tokenId: number,
  currentPassword: string
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/settings/ai-tokens/${tokenId}/test`, {
    method: 'POST',
    headers: stateChangingHeaders(),
    credentials: 'include',
    body: JSON.stringify({ current_password: currentPassword })
  })
  await throwOnError(res)
  return res.json()
}

export async function revealToken(
  tokenId: number,
  currentPassword: string
): Promise<{ token: string }> {
  const res = await fetch(`${API_BASE}/settings/ai-tokens/${tokenId}/reveal`, {
    method: 'POST',
    headers: stateChangingHeaders(),
    credentials: 'include',
    body: JSON.stringify({ current_password: currentPassword })
  })
  await throwOnError(res)
  return res.json()
}

export async function setDefaultToken(tokenId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/settings/ai-tokens/${tokenId}/default`, {
    method: 'PUT',
    headers: stateChangingHeaders(),
    credentials: 'include'
  })
  await throwOnError(res)
}

// ---------------------------------------------------------------------------
// Toast notifications (same pattern as dashboard.ts)
// ---------------------------------------------------------------------------

function showToast(message: string, variant: 'success' | 'danger' = 'success'): void {
  const toast = document.createElement('div')
  toast.className = `alert alert-${variant} position-fixed bottom-0 end-0 m-3`
  toast.style.zIndex = '9999'
  toast.textContent = message
  document.body.appendChild(toast)
  setTimeout(() => toast.remove(), 3500)
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function providerLabel(provider: string): string {
  const map: Record<string, string> = {
    minimax: 'MiniMax'
  }
  return map[provider] ?? provider
}

// ---------------------------------------------------------------------------
// Modal helpers — Bootstrap 5 programmatic modals
// ---------------------------------------------------------------------------

/** Remove all AI-token modals from the DOM (called before injecting fresh ones). */
function removeExistingModals(): void {
  document.querySelectorAll('[data-ai-token-modal]').forEach((el) => el.remove())
  // Also clean up any lingering Bootstrap backdrops
  document.querySelectorAll('.modal-backdrop').forEach((el) => el.remove())
  document.body.classList.remove('modal-open')
  document.body.style.removeProperty('overflow')
  document.body.style.removeProperty('padding-right')
}

function injectModal(html: string): HTMLElement {
  const wrapper = document.createElement('div')
  wrapper.setAttribute('data-ai-token-modal', 'true')
  wrapper.innerHTML = html
  document.body.appendChild(wrapper)
  return wrapper
}

// ---------------------------------------------------------------------------
// Token list rendering
// ---------------------------------------------------------------------------

function renderTokenRow(token: AIToken): string {
  const providerBadge = `<span class="badge text-bg-secondary">${escapeHtml(providerLabel(token.provider))}</span>`
  const defaultBadge = token.is_default
    ? `<span class="badge text-bg-success ms-1">Default</span>`
    : ''
  const reentryWarning = token.needs_reentry
    ? `<span class="badge text-bg-warning ms-1" title="Token needs to be re-entered after password reset">
         <i class="ri-error-warning-line"></i> Needs Re-entry
       </span>`
    : ''

  const maskDisplay = token.token_mask || (token.token_last4 ? `****${token.token_last4}` : '••••••••')

  const setDefaultBtn = !token.is_default
    ? `<button class="btn btn-sm btn-outline-secondary" data-ai-action="set-default" data-token-id="${token.id}" title="Set as Default">
         <i class="ri-star-line"></i>
       </button>`
    : `<button class="btn btn-sm btn-outline-warning" disabled title="Already Default">
         <i class="ri-star-fill"></i>
       </button>`

  return `
    <tr data-token-row="${token.id}">
      <td>${providerBadge}</td>
      <td>${escapeHtml(token.label)}${defaultBadge}${reentryWarning}</td>
      <td><code>${escapeHtml(maskDisplay)}</code></td>
      <td class="text-muted small">${escapeHtml(formatDate(token.last_used_at))}</td>
      <td>
        <div class="d-flex gap-1 flex-wrap">
          <button class="btn btn-sm btn-outline-secondary" data-ai-action="reveal" data-token-id="${token.id}" title="Reveal Token">
            <i class="ri-eye-line"></i>
          </button>
          <button class="btn btn-sm btn-outline-secondary" data-ai-action="test" data-token-id="${token.id}" title="Test Connection">
            <i class="ri-play-line"></i>
          </button>
          <button class="btn btn-sm btn-outline-secondary" data-ai-action="edit" data-token-id="${token.id}" title="Update Token">
            <i class="ri-pencil-line"></i>
          </button>
          ${setDefaultBtn}
          <button class="btn btn-sm btn-outline-danger" data-ai-action="delete" data-token-id="${token.id}" data-token-label="${escapeAttr(token.label)}" title="Delete">
            <i class="ri-delete-bin-line"></i>
          </button>
        </div>
      </td>
    </tr>`
}

function renderTokenList(container: HTMLElement, tokens: AIToken[]): void {
  if (tokens.length === 0) {
    container.innerHTML = `
      <div class="text-center py-5 text-muted" id="ai-tokens-empty">
        <i class="ri-key-2-line fs-2 d-block mb-2"></i>
        <p class="mb-0">No AI tokens configured. Add one to use your own API key.</p>
      </div>`
    return
  }

  const rows = tokens.map(renderTokenRow).join('')
  container.innerHTML = `
    <div class="table-responsive">
      <table class="table table-hover align-middle mb-0">
        <thead>
          <tr>
            <th>Provider</th>
            <th>Label</th>
            <th>Token</th>
            <th>Last Used</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`
}

// ---------------------------------------------------------------------------
// Add / Edit Token Modal
// ---------------------------------------------------------------------------

function openAddTokenModal(onSuccess: () => void): void {
  removeExistingModals()

  const html = `
    <div class="modal fade" id="ai-token-add-modal" tabindex="-1" aria-labelledby="ai-token-add-title" aria-modal="true" role="dialog">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="ai-token-add-title">
              <i class="ri-key-2-line me-2"></i>Add AI Service Token
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <div id="ai-token-add-alert" class="alert alert-danger d-none" role="alert"></div>
            <form id="ai-token-add-form" novalidate>
              <div class="mb-3">
                <label class="form-label required" for="add-provider">Provider</label>
                <select class="form-select" id="add-provider" required>
                  <option value="minimax" selected>MiniMax</option>
                </select>
              </div>
              <div class="mb-3">
                <label class="form-label required" for="add-label">Label</label>
                <input type="text" class="form-control" id="add-label" placeholder="e.g. My MiniMax Key" required maxlength="100" autocomplete="off" />
                <div class="form-text">A short description to identify this token.</div>
              </div>
              <div class="mb-3">
                <label class="form-label required" for="add-token-value">Token</label>
                <div class="input-group">
                  <input type="password" class="form-control" id="add-token-value" placeholder="Paste your API token here" required autocomplete="new-password" />
                  <button class="btn btn-outline-secondary" type="button" id="add-token-toggle" title="Toggle visibility" aria-label="Toggle token visibility">
                    <i class="ri-eye-line" id="add-token-toggle-icon"></i>
                  </button>
                </div>
              </div>
              <div class="mb-3">
                <label class="form-label required" for="add-current-password">Your Current Password</label>
                <input type="password" class="form-control" id="add-current-password" placeholder="Enter your account password" required autocomplete="current-password" />
                <div class="form-text">Required to encrypt the token securely with your password.</div>
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            <button type="button" class="btn btn-primary" id="ai-token-add-submit">
              <span id="ai-token-add-spinner" class="spinner-border spinner-border-sm me-1 d-none" role="status"></span>
              <i class="ri-save-3-line me-1"></i>Save Token
            </button>
          </div>
        </div>
      </div>
    </div>`

  const wrapper = injectModal(html)
  const modalEl = wrapper.querySelector('#ai-token-add-modal') as HTMLElement
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const bsModal = new (window as any).bootstrap.Modal(modalEl)

  // Toggle password visibility for token input
  const tokenInput = modalEl.querySelector('#add-token-value') as HTMLInputElement
  const toggleBtn = modalEl.querySelector('#add-token-toggle') as HTMLButtonElement
  const toggleIcon = modalEl.querySelector('#add-token-toggle-icon') as HTMLElement
  toggleBtn.addEventListener('click', () => {
    const isPassword = tokenInput.type === 'password'
    tokenInput.type = isPassword ? 'text' : 'password'
    toggleIcon.className = isPassword ? 'ri-eye-off-line' : 'ri-eye-line'
  })

  // Submit handler
  const submitBtn = modalEl.querySelector('#ai-token-add-submit') as HTMLButtonElement
  const spinner = modalEl.querySelector('#ai-token-add-spinner') as HTMLElement
  const alertEl = modalEl.querySelector('#ai-token-add-alert') as HTMLElement

  submitBtn.addEventListener('click', async () => {
    const provider = (modalEl.querySelector('#add-provider') as HTMLSelectElement).value
    const label = (modalEl.querySelector('#add-label') as HTMLInputElement).value.trim()
    const tokenValue = tokenInput.value
    const currentPassword = (modalEl.querySelector('#add-current-password') as HTMLInputElement).value

    alertEl.classList.add('d-none')

    if (!provider || !label || !tokenValue || !currentPassword) {
      alertEl.textContent = 'All fields are required.'
      alertEl.classList.remove('d-none')
      return
    }

    submitBtn.disabled = true
    spinner.classList.remove('d-none')

    try {
      await createToken(provider, label, tokenValue, currentPassword)
      // Clear sensitive fields before closing
      tokenInput.value = ''
      ;(modalEl.querySelector('#add-current-password') as HTMLInputElement).value = ''
      bsModal.hide()
      showToast('Token saved successfully.')
      onSuccess()
    } catch (err) {
      alertEl.textContent = err instanceof Error ? err.message : 'Failed to save token.'
      alertEl.classList.remove('d-none')
    } finally {
      submitBtn.disabled = false
      spinner.classList.add('d-none')
    }
  })

  // Clear sensitive data when modal closes
  modalEl.addEventListener('hidden.bs.modal', () => {
    tokenInput.value = ''
    ;(modalEl.querySelector('#add-current-password') as HTMLInputElement).value = ''
    // Ensure type is reset to password so nothing lingers in plaintext
    tokenInput.type = 'password'
    toggleIcon.className = 'ri-eye-line'
    removeExistingModals()
  })

  bsModal.show()
}

// ---------------------------------------------------------------------------
// Edit Token Modal (update token value)
// ---------------------------------------------------------------------------

function openEditTokenModal(token: AIToken, onSuccess: () => void): void {
  removeExistingModals()

  const html = `
    <div class="modal fade" id="ai-token-edit-modal" tabindex="-1" aria-labelledby="ai-token-edit-title" aria-modal="true" role="dialog">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="ai-token-edit-title">
              <i class="ri-pencil-line me-2"></i>Update Token — ${escapeHtml(token.label)}
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <div id="ai-token-edit-alert" class="alert alert-danger d-none" role="alert"></div>
            <p class="text-muted small mb-3">
              Current token: <code>${escapeHtml(token.token_mask || (token.token_last4 ? `****${token.token_last4}` : '••••••••'))}</code>
            </p>
            <form id="ai-token-edit-form" novalidate>
              <div class="mb-3">
                <label class="form-label required" for="edit-token-value">New Token Value</label>
                <div class="input-group">
                  <input type="password" class="form-control" id="edit-token-value" placeholder="Paste new API token here" required autocomplete="new-password" />
                  <button class="btn btn-outline-secondary" type="button" id="edit-token-toggle" title="Toggle visibility" aria-label="Toggle token visibility">
                    <i class="ri-eye-line" id="edit-token-toggle-icon"></i>
                  </button>
                </div>
              </div>
              <div class="mb-3">
                <label class="form-label required" for="edit-current-password">Your Current Password</label>
                <input type="password" class="form-control" id="edit-current-password" placeholder="Enter your account password" required autocomplete="current-password" />
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            <button type="button" class="btn btn-primary" id="ai-token-edit-submit">
              <span id="ai-token-edit-spinner" class="spinner-border spinner-border-sm me-1 d-none" role="status"></span>
              <i class="ri-save-3-line me-1"></i>Update Token
            </button>
          </div>
        </div>
      </div>
    </div>`

  const wrapper = injectModal(html)
  const modalEl = wrapper.querySelector('#ai-token-edit-modal') as HTMLElement
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const bsModal = new (window as any).bootstrap.Modal(modalEl)

  const tokenInput = modalEl.querySelector('#edit-token-value') as HTMLInputElement
  const toggleBtn = modalEl.querySelector('#edit-token-toggle') as HTMLButtonElement
  const toggleIcon = modalEl.querySelector('#edit-token-toggle-icon') as HTMLElement
  toggleBtn.addEventListener('click', () => {
    const isPassword = tokenInput.type === 'password'
    tokenInput.type = isPassword ? 'text' : 'password'
    toggleIcon.className = isPassword ? 'ri-eye-off-line' : 'ri-eye-line'
  })

  const submitBtn = modalEl.querySelector('#ai-token-edit-submit') as HTMLButtonElement
  const spinner = modalEl.querySelector('#ai-token-edit-spinner') as HTMLElement
  const alertEl = modalEl.querySelector('#ai-token-edit-alert') as HTMLElement

  submitBtn.addEventListener('click', async () => {
    const tokenValue = tokenInput.value
    const currentPassword = (modalEl.querySelector('#edit-current-password') as HTMLInputElement).value

    alertEl.classList.add('d-none')

    if (!tokenValue || !currentPassword) {
      alertEl.textContent = 'New token value and current password are required.'
      alertEl.classList.remove('d-none')
      return
    }

    submitBtn.disabled = true
    spinner.classList.remove('d-none')

    try {
      await updateToken(token.id, tokenValue, currentPassword)
      tokenInput.value = ''
      ;(modalEl.querySelector('#edit-current-password') as HTMLInputElement).value = ''
      bsModal.hide()
      showToast('Token updated successfully.')
      onSuccess()
    } catch (err) {
      alertEl.textContent = err instanceof Error ? err.message : 'Failed to update token.'
      alertEl.classList.remove('d-none')
    } finally {
      submitBtn.disabled = false
      spinner.classList.add('d-none')
    }
  })

  modalEl.addEventListener('hidden.bs.modal', () => {
    tokenInput.value = ''
    ;(modalEl.querySelector('#edit-current-password') as HTMLInputElement).value = ''
    tokenInput.type = 'password'
    toggleIcon.className = 'ri-eye-line'
    removeExistingModals()
  })

  bsModal.show()
}

// ---------------------------------------------------------------------------
// Reveal Token Modal
// ---------------------------------------------------------------------------

function openRevealTokenModal(token: AIToken): void {
  removeExistingModals()

  const html = `
    <div class="modal fade" id="ai-token-reveal-modal" tabindex="-1" aria-labelledby="ai-token-reveal-title" aria-modal="true" role="dialog">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="ai-token-reveal-title">
              <i class="ri-eye-line me-2"></i>Reveal Token — ${escapeHtml(token.label)}
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <div id="ai-token-reveal-alert" class="alert alert-danger d-none" role="alert"></div>
            <div id="ai-token-reveal-password-section">
              <p class="text-muted small">Enter your current password to view this token.</p>
              <div class="mb-3">
                <label class="form-label required" for="reveal-current-password">Current Password</label>
                <input type="password" class="form-control" id="reveal-current-password" placeholder="Enter your account password" autocomplete="current-password" />
              </div>
              <button type="button" class="btn btn-primary" id="ai-token-reveal-submit">
                <span id="ai-token-reveal-spinner" class="spinner-border spinner-border-sm me-1 d-none" role="status"></span>
                <i class="ri-eye-line me-1"></i>Reveal
              </button>
            </div>
            <div id="ai-token-reveal-result" class="d-none mt-3">
              <label class="form-label">Token Plaintext</label>
              <div class="input-group">
                <input type="text" class="form-control font-monospace" id="ai-token-reveal-value" readonly aria-label="Revealed token value" />
                <button class="btn btn-outline-secondary" type="button" id="ai-token-reveal-copy" title="Copy to clipboard">
                  <i class="ri-clipboard-line"></i>
                </button>
              </div>
              <div class="form-text text-warning mt-1">
                <i class="ri-error-warning-line me-1"></i>This value will be cleared when the dialog closes.
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
          </div>
        </div>
      </div>
    </div>`

  const wrapper = injectModal(html)
  const modalEl = wrapper.querySelector('#ai-token-reveal-modal') as HTMLElement
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const bsModal = new (window as any).bootstrap.Modal(modalEl)

  const submitBtn = modalEl.querySelector('#ai-token-reveal-submit') as HTMLButtonElement
  const spinner = modalEl.querySelector('#ai-token-reveal-spinner') as HTMLElement
  const alertEl = modalEl.querySelector('#ai-token-reveal-alert') as HTMLElement
  const passwordSection = modalEl.querySelector('#ai-token-reveal-password-section') as HTMLElement
  const resultSection = modalEl.querySelector('#ai-token-reveal-result') as HTMLElement
  const revealValueInput = modalEl.querySelector('#ai-token-reveal-value') as HTMLInputElement
  const copyBtn = modalEl.querySelector('#ai-token-reveal-copy') as HTMLButtonElement

  submitBtn.addEventListener('click', async () => {
    const currentPassword = (modalEl.querySelector('#reveal-current-password') as HTMLInputElement).value
    alertEl.classList.add('d-none')

    if (!currentPassword) {
      alertEl.textContent = 'Current password is required.'
      alertEl.classList.remove('d-none')
      return
    }

    submitBtn.disabled = true
    spinner.classList.remove('d-none')

    try {
      const result = await revealToken(token.id, currentPassword)
      // Clear password field immediately after successful call
      ;(modalEl.querySelector('#reveal-current-password') as HTMLInputElement).value = ''

      // Show plaintext — set directly into DOM, do not log
      revealValueInput.value = result.token
      // Immediately remove the token from the result object to minimize lifetime
      // (TypeScript doesn't allow delete on non-optional, so reassign instead)
      Object.assign(result, { token: '' })

      passwordSection.classList.add('d-none')
      resultSection.classList.remove('d-none')
    } catch (err) {
      alertEl.textContent = err instanceof Error ? err.message : 'Failed to reveal token.'
      alertEl.classList.remove('d-none')
    } finally {
      submitBtn.disabled = false
      spinner.classList.add('d-none')
    }
  })

  copyBtn.addEventListener('click', async () => {
    const value = revealValueInput.value
    if (!value) return
    try {
      await navigator.clipboard.writeText(value)
      copyBtn.innerHTML = '<i class="ri-check-line"></i>'
      setTimeout(() => {
        copyBtn.innerHTML = '<i class="ri-clipboard-line"></i>'
      }, 2000)
    } catch {
      showToast('Failed to copy token to clipboard.', 'danger')
    }
  })

  // CRITICAL: Clear plaintext from DOM immediately on close
  modalEl.addEventListener('hide.bs.modal', () => {
    revealValueInput.value = ''
    ;(modalEl.querySelector('#reveal-current-password') as HTMLInputElement).value = ''
  })

  modalEl.addEventListener('hidden.bs.modal', () => {
    removeExistingModals()
  })

  bsModal.show()
}

// ---------------------------------------------------------------------------
// Test Token Modal
// ---------------------------------------------------------------------------

function openTestTokenModal(token: AIToken): void {
  removeExistingModals()

  const html = `
    <div class="modal fade" id="ai-token-test-modal" tabindex="-1" aria-labelledby="ai-token-test-title" aria-modal="true" role="dialog">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="ai-token-test-title">
              <i class="ri-play-line me-2"></i>Test Token — ${escapeHtml(token.label)}
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <div id="ai-token-test-alert" class="alert alert-danger d-none" role="alert"></div>
            <div id="ai-token-test-password-section">
              <p class="text-muted small">Enter your current password to decrypt and test the token.</p>
              <div class="mb-3">
                <label class="form-label required" for="test-current-password">Current Password</label>
                <input type="password" class="form-control" id="test-current-password" placeholder="Enter your account password" autocomplete="current-password" />
              </div>
              <button type="button" class="btn btn-primary" id="ai-token-test-submit">
                <span id="ai-token-test-spinner" class="spinner-border spinner-border-sm me-1 d-none" role="status"></span>
                <i class="ri-play-line me-1"></i>Run Test
              </button>
            </div>
            <div id="ai-token-test-result" class="d-none mt-3"></div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
          </div>
        </div>
      </div>
    </div>`

  const wrapper = injectModal(html)
  const modalEl = wrapper.querySelector('#ai-token-test-modal') as HTMLElement
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const bsModal = new (window as any).bootstrap.Modal(modalEl)

  const submitBtn = modalEl.querySelector('#ai-token-test-submit') as HTMLButtonElement
  const spinner = modalEl.querySelector('#ai-token-test-spinner') as HTMLElement
  const alertEl = modalEl.querySelector('#ai-token-test-alert') as HTMLElement
  const resultSection = modalEl.querySelector('#ai-token-test-result') as HTMLElement

  submitBtn.addEventListener('click', async () => {
    const currentPassword = (modalEl.querySelector('#test-current-password') as HTMLInputElement).value
    alertEl.classList.add('d-none')
    resultSection.classList.add('d-none')

    if (!currentPassword) {
      alertEl.textContent = 'Current password is required.'
      alertEl.classList.remove('d-none')
      return
    }

    submitBtn.disabled = true
    spinner.classList.remove('d-none')

    try {
      const result = await testToken(token.id, currentPassword)
      ;(modalEl.querySelector('#test-current-password') as HTMLInputElement).value = ''

      if (result.success) {
        resultSection.innerHTML = `
          <div class="alert alert-success d-flex align-items-center" role="alert">
            <i class="ri-checkbox-circle-line me-2 fs-5"></i>
            <div><strong>Connection successful.</strong> ${escapeHtml(result.message)}</div>
          </div>`
      } else {
        resultSection.innerHTML = `
          <div class="alert alert-warning d-flex align-items-center" role="alert">
            <i class="ri-error-warning-line me-2 fs-5"></i>
            <div><strong>Connection failed.</strong> ${escapeHtml(result.message)}</div>
          </div>`
      }
      resultSection.classList.remove('d-none')
    } catch (err) {
      alertEl.textContent = err instanceof Error ? err.message : 'Failed to test token.'
      alertEl.classList.remove('d-none')
    } finally {
      submitBtn.disabled = false
      spinner.classList.add('d-none')
    }
  })

  modalEl.addEventListener('hidden.bs.modal', () => {
    ;(modalEl.querySelector('#test-current-password') as HTMLInputElement).value = ''
    removeExistingModals()
  })

  bsModal.show()
}

// ---------------------------------------------------------------------------
// Page initialiser — exported entry point
// ---------------------------------------------------------------------------

export async function initAITokensPage(): Promise<void> {
  const container = document.getElementById('ai-tokens-list')
  if (!container || container.dataset.inited) return
  container.dataset.inited = 'true'

  // Show loading
  container.innerHTML = `
    <div class="text-center py-4">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Loading...</span>
      </div>
      <p class="text-muted mt-2">Loading tokens...</p>
    </div>`

  // Keep a module-level token cache for action lookups
  let tokens: AIToken[] = []

  const loadTokens = async () => {
    try {
      tokens = await listTokens()
      renderTokenList(container, tokens)
    } catch (err) {
      container.innerHTML = `
        <div class="alert alert-danger" role="alert">
          <i class="ri-error-warning-line me-2"></i>
          Failed to load tokens: ${escapeHtml(err instanceof Error ? err.message : String(err))}
        </div>`
    }
  }

  // Wire "Add Token" button
  const addBtn = document.getElementById('ai-tokens-add-btn')
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      openAddTokenModal(loadTokens)
    })
  }

  // Event delegation on the list container for action buttons
  container.addEventListener('click', async (e) => {
    const target = (e.target as HTMLElement).closest<HTMLElement>('[data-ai-action]')
    if (!target) return

    const action = target.dataset.aiAction
    const tokenId = Number(target.dataset.tokenId)
    const token = tokens.find((t) => t.id === tokenId)
    if (!token) return

    if (action === 'reveal') {
      openRevealTokenModal(token)
    } else if (action === 'test') {
      openTestTokenModal(token)
    } else if (action === 'edit') {
      openEditTokenModal(token, loadTokens)
    } else if (action === 'set-default') {
      target.classList.add('disabled')
      try {
        await setDefaultToken(tokenId)
        showToast('Default token updated.')
        await loadTokens()
      } catch (err) {
        showToast(err instanceof Error ? err.message : 'Failed to set default.', 'danger')
        target.classList.remove('disabled')
      }
    } else if (action === 'delete') {
      const tokenLabel = target.dataset.tokenLabel || token.label
      if (!window.confirm(`Delete token "${tokenLabel}"? This cannot be undone.`)) return
      target.classList.add('disabled')
      try {
        await deleteToken(tokenId)
        showToast('Token deleted.')
        await loadTokens()
      } catch (err) {
        showToast(err instanceof Error ? err.message : 'Failed to delete token.', 'danger')
        target.classList.remove('disabled')
      }
    }
  })

  await loadTokens()
}
