/* global fetch */
/**
 * ai-service.ts — Settings / AI Service page handler
 *
 * Implements AI provider CRUD, reorder, enable/disable, test, and reveal flows.
 * Uses direct fetch calls (credentials: "include", CSRF header) consistent with
 * ai-tokens.ts patterns.
 *
 * Security considerations:
 * - API keys are NEVER stored in module-level variables.
 * - Reveal modal clears plaintext from the DOM immediately on close.
 * - No console.log of key values.
 * - All state-changing requests include the X-CSRF-Token header.
 */

import { escapeHtml, escapeAttr } from '@/scripts/utils'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const API_BASE = import.meta.env.DEV ? 'http://localhost:8088' : ''
const PROVIDERS_BASE = `${API_BASE}/settings/ai-providers`

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AIProvider {
  id: number
  user_id: number
  label: string
  protocol: string
  base_url: string
  model: string
  api_key_mask: string
  temperature: number | null
  max_tokens: number
  thinking: boolean
  effort: string
  enabled: boolean
  priority: number
  revision: number
  created_at: string
  updated_at: string
}

interface RuntimeStatus {
  chain: { id: number; label: string; protocol: string }[]
  environment_fallback: boolean
  environment_provider?: string
  [key: string]: unknown
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

async function extractErrorBody(res: Response): Promise<{ message: string; code?: string }> {
  try {
    const body = await res.json()
    return { message: body.detail || `HTTP ${res.status}`, code: body.code }
  } catch {
    return { message: `HTTP ${res.status}` }
  }
}

async function throwOnError(res: Response): Promise<void> {
  if (!res.ok) {
    if (res.status === 401) {
      window.location.href = '/authentication/modern/login'
      throw new Error('Unauthorized')
    }
    const { message } = await extractErrorBody(res)
    throw new Error(message)
  }
}

/** Returns the error code if present (e.g. "revision_conflict"), otherwise throws normally */
async function throwOnErrorWithCode(res: Response): Promise<void> {
  if (!res.ok) {
    if (res.status === 401) {
      window.location.href = '/authentication/modern/login'
      throw new Error('Unauthorized')
    }
    const { message, code } = await extractErrorBody(res)
    const err = new Error(message) as Error & { code?: string }
    err.code = code
    throw err
  }
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function listProviders(): Promise<AIProvider[]> {
  const res = await fetch(PROVIDERS_BASE, { credentials: 'include' })
  await throwOnError(res)
  const data = await res.json()
  return Array.isArray(data) ? data : (data.providers ?? [])
}

async function getRuntimeStatus(): Promise<RuntimeStatus> {
  const res = await fetch(`${PROVIDERS_BASE}/runtime-status`, { credentials: 'include' })
  await throwOnError(res)
  return res.json()
}

async function createProvider(payload: {
  label: string
  protocol: string
  base_url: string
  model: string
  api_key: string
  temperature: number | null
  max_tokens: number
  thinking: boolean
  effort: string
}): Promise<AIProvider> {
  const res = await fetch(PROVIDERS_BASE, {
    method: 'POST',
    headers: stateChangingHeaders(),
    credentials: 'include',
    body: JSON.stringify(payload)
  })
  await throwOnErrorWithCode(res)
  return res.json()
}

async function updateProvider(
  id: number,
  payload: {
    revision: number
    label?: string
    protocol?: string
    base_url?: string
    model?: string
    api_key?: string
    temperature?: number | null
    max_tokens?: number
    thinking?: boolean
    effort?: string
  }
): Promise<AIProvider> {
  const res = await fetch(`${PROVIDERS_BASE}/${id}`, {
    method: 'PUT',
    headers: stateChangingHeaders(),
    credentials: 'include',
    body: JSON.stringify(payload)
  })
  await throwOnErrorWithCode(res)
  return res.json()
}

async function deleteProvider(id: number, revision: number): Promise<void> {
  const res = await fetch(`${PROVIDERS_BASE}/${id}`, {
    method: 'DELETE',
    headers: stateChangingHeaders(),
    credentials: 'include',
    body: JSON.stringify({ revision })
  })
  await throwOnErrorWithCode(res)
}

async function testProvider(id: number): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${PROVIDERS_BASE}/${id}/test`, {
    method: 'POST',
    headers: stateChangingHeaders(),
    credentials: 'include'
  })
  await throwOnError(res)
  return res.json()
}

async function revealProviderKey(
  id: number,
  currentPassword: string
): Promise<{ api_key: string }> {
  const res = await fetch(`${PROVIDERS_BASE}/${id}/reveal`, {
    method: 'POST',
    headers: stateChangingHeaders(),
    credentials: 'include',
    body: JSON.stringify({ current_password: currentPassword })
  })
  await throwOnError(res)
  return res.json()
}

async function setProviderEnabled(id: number, enabled: boolean): Promise<AIProvider> {
  const res = await fetch(`${PROVIDERS_BASE}/${id}/enabled`, {
    method: 'PUT',
    headers: stateChangingHeaders(),
    credentials: 'include',
    body: JSON.stringify({ enabled })
  })
  await throwOnError(res)
  return res.json()
}

async function reorderProviders(
  orderedIds: number[],
  revision: number
): Promise<AIProvider[]> {
  const res = await fetch(`${PROVIDERS_BASE}/order`, {
    method: 'PUT',
    headers: stateChangingHeaders(),
    credentials: 'include',
    body: JSON.stringify({ ordered_ids: orderedIds, revision })
  })
  await throwOnErrorWithCode(res)
  return res.json()
}

async function discoverModels(payload: {
  protocol: string
  base_url: string
  api_key?: string
  provider_id?: number
}): Promise<{ models: { id: string; display_name: string }[]; manual_entry_allowed?: boolean; warning?: string | null }> {
  const res = await fetch(`${PROVIDERS_BASE}/actions/discover-models`, {
    method: 'POST',
    headers: stateChangingHeaders(),
    credentials: 'include',
    body: JSON.stringify(payload)
  })
  await throwOnError(res)
  return res.json()
}

// ---------------------------------------------------------------------------
// Toast notifications
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
// Revision conflict helper
// ---------------------------------------------------------------------------

function handleRevisionConflict(err: unknown, reloadFn: () => Promise<void>): boolean {
  if (err instanceof Error && (err as Error & { code?: string }).code === 'revision_conflict') {
    alert('Provider settings have changed. Reloading...')
    reloadFn().catch(() => undefined)
    return true
  }
  return false
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function protocolBadgeClass(protocol: string): string {
  const map: Record<string, string> = {
    openai: 'text-bg-success',
    anthropic: 'text-bg-warning',
    gemini: 'text-bg-info'
  }
  return map[protocol] ?? 'text-bg-secondary'
}

function truncateUrl(url: string, max = 40): string {
  if (url.length <= max) return url
  return url.slice(0, max) + '…'
}

// ---------------------------------------------------------------------------
// Modal helpers — Bootstrap 5 programmatic modals
// ---------------------------------------------------------------------------

function removeExistingModals(): void {
  document.querySelectorAll('[data-ai-service-modal]').forEach((el) => el.remove())
  document.querySelectorAll('.modal-backdrop').forEach((el) => el.remove())
  document.body.classList.remove('modal-open')
  document.body.style.removeProperty('overflow')
  document.body.style.removeProperty('padding-right')
}

function injectModal(html: string): HTMLElement {
  const wrapper = document.createElement('div')
  wrapper.setAttribute('data-ai-service-modal', 'true')
  wrapper.innerHTML = html
  document.body.appendChild(wrapper)
  return wrapper
}

// ---------------------------------------------------------------------------
// Provider list rendering
// ---------------------------------------------------------------------------

function renderProviderRow(provider: AIProvider, isFirst: boolean, isLast: boolean): string {
  const protocolClass = protocolBadgeClass(provider.protocol)
  const protocolBadge = `<span class="badge ${protocolClass}">${escapeHtml(provider.protocol)}</span>`

  const enabledSwitch = `
    <div class="form-check form-switch mb-0">
      <input class="form-check-input" type="checkbox" role="switch"
        data-ai-action="toggle-enabled"
        data-provider-id="${provider.id}"
        ${provider.enabled ? 'checked' : ''}
        aria-label="Enable ${escapeAttr(provider.label)}"
      />
    </div>`

  const upBtn = `
    <button class="btn btn-sm btn-outline-secondary" data-ai-action="move-up" data-provider-id="${provider.id}" title="Move Up" ${isFirst ? 'disabled' : ''}>
      <i class="ri-arrow-up-line"></i>
    </button>`
  const downBtn = `
    <button class="btn btn-sm btn-outline-secondary" data-ai-action="move-down" data-provider-id="${provider.id}" title="Move Down" ${isLast ? 'disabled' : ''}>
      <i class="ri-arrow-down-line"></i>
    </button>`

  return `
    <tr data-provider-row="${provider.id}">
      <td>
        <div class="d-flex gap-1">
          ${upBtn}
          ${downBtn}
        </div>
      </td>
      <td>${enabledSwitch}</td>
      <td>${escapeHtml(provider.label)}</td>
      <td>${protocolBadge}</td>
      <td><span class="font-monospace small">${escapeHtml(provider.model)}</span></td>
      <td>
        <span class="text-muted small" title="${escapeAttr(provider.base_url)}">
          ${escapeHtml(truncateUrl(provider.base_url))}
        </span>
      </td>
      <td>
        <div class="d-flex gap-1 flex-wrap">
          <button class="btn btn-sm btn-outline-secondary" data-ai-action="edit" data-provider-id="${provider.id}" title="Edit">
            <i class="ri-pencil-line"></i>
          </button>
          <button class="btn btn-sm btn-outline-secondary" data-ai-action="test" data-provider-id="${provider.id}" title="Test Connection">
            <i class="ri-play-line"></i>
          </button>
          <button class="btn btn-sm btn-outline-secondary" data-ai-action="reveal" data-provider-id="${provider.id}" title="Reveal API Key">
            <i class="ri-eye-line"></i>
          </button>
          <button class="btn btn-sm btn-outline-danger" data-ai-action="delete" data-provider-id="${provider.id}" data-provider-label="${escapeAttr(provider.label)}" title="Delete">
            <i class="ri-delete-bin-line"></i>
          </button>
        </div>
      </td>
    </tr>`
}

function renderProviderList(container: HTMLElement, providers: AIProvider[]): void {
  if (providers.length === 0) {
    container.innerHTML = `
      <div class="text-center py-5 text-muted" id="ai-providers-empty">
        <i class="ri-robot-line fs-2 d-block mb-2"></i>
        <p class="mb-0">No AI providers configured. Add one to get started.</p>
      </div>`
    return
  }

  const rows = providers.map((p, i) =>
    renderProviderRow(p, i === 0, i === providers.length - 1)
  ).join('')

  container.innerHTML = `
    <div class="table-responsive">
      <table class="table table-hover align-middle mb-0">
        <thead>
          <tr>
            <th style="width:80px">Order</th>
            <th style="width:60px">Enabled</th>
            <th>Label</th>
            <th>Protocol</th>
            <th>Model</th>
            <th>Base URL</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`
}

// ---------------------------------------------------------------------------
// Add / Edit Provider Modal
// ---------------------------------------------------------------------------

function buildProviderModalHtml(
  mode: 'add' | 'edit',
  provider?: AIProvider
): string {
  const isEdit = mode === 'edit'
  const titleIcon = isEdit ? 'ri-pencil-line' : 'ri-add-line'
  const titleText = isEdit ? `Edit Provider — ${escapeHtml(provider!.label)}` : 'Add AI Provider'
  const modalId = 'ai-provider-form-modal'

  const labelVal = isEdit ? escapeAttr(provider!.label) : ''
  const protocolVal = isEdit ? provider!.protocol : 'openai'
  const baseUrlVal = isEdit ? escapeAttr(provider!.base_url) : ''
  const modelVal = isEdit ? escapeAttr(provider!.model) : ''
  const tempVal = isEdit && provider!.temperature !== null ? String(provider!.temperature) : ''
  const maxTokensVal = isEdit ? String(provider!.max_tokens) : '4096'
  const thinkingChecked = isEdit && provider!.thinking ? 'checked' : ''
  const effortVal = isEdit ? provider!.effort : 'low'

  const protocolOptions = ['openai', 'anthropic', 'gemini'].map((p) =>
    `<option value="${p}" ${p === protocolVal ? 'selected' : ''}>${p}</option>`
  ).join('')

  const effortOptions = ['low', 'medium', 'high'].map((e) =>
    `<option value="${e}" ${e === effortVal ? 'selected' : ''}>${e}</option>`
  ).join('')

  const apiKeySection = isEdit
    ? `
        <div class="mb-3">
          <label class="form-label" for="prov-api-key">API Key</label>
          <div class="form-text mb-2">Current: <code>${escapeHtml(provider!.api_key_mask || '••••••••')}</code></div>
          <div class="form-check mb-2">
            <input class="form-check-input" type="checkbox" id="prov-update-key-check" />
            <label class="form-check-label" for="prov-update-key-check">Update API key</label>
          </div>
          <div id="prov-api-key-wrapper" class="d-none">
            <div class="input-group">
              <input type="password" class="form-control" id="prov-api-key" placeholder="Enter new API key" autocomplete="new-password" />
              <button class="btn btn-outline-secondary" type="button" id="prov-api-key-toggle" title="Toggle visibility" aria-label="Toggle API key visibility">
                <i class="ri-eye-line" id="prov-api-key-toggle-icon"></i>
              </button>
            </div>
          </div>
        </div>`
    : `
        <div class="mb-3">
          <label class="form-label required" for="prov-api-key">API Key</label>
          <div class="input-group">
            <input type="password" class="form-control" id="prov-api-key" placeholder="Enter API key" required autocomplete="new-password" />
            <button class="btn btn-outline-secondary" type="button" id="prov-api-key-toggle" title="Toggle visibility" aria-label="Toggle API key visibility">
              <i class="ri-eye-line" id="prov-api-key-toggle-icon"></i>
            </button>
          </div>
        </div>`

  return `
    <div class="modal fade" id="${modalId}" tabindex="-1" aria-labelledby="prov-modal-title" aria-modal="true" role="dialog">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="prov-modal-title">
              <i class="${titleIcon} me-2"></i>${titleText}
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <div id="prov-modal-alert" class="alert alert-danger d-none" role="alert"></div>
            <form id="prov-modal-form" novalidate>
              <div class="row g-3">
                <div class="col-md-6">
                  <label class="form-label required" for="prov-label">Label</label>
                  <input type="text" class="form-control" id="prov-label" value="${labelVal}" placeholder="e.g. My GPT-4o" required maxlength="100" autocomplete="off" />
                </div>
                <div class="col-md-6">
                  <label class="form-label required" for="prov-protocol">Protocol</label>
                  <select class="form-select" id="prov-protocol" required>
                    ${protocolOptions}
                  </select>
                </div>
                <div class="col-12">
                  <label class="form-label required" for="prov-base-url">Base URL</label>
                  <input type="url" class="form-control" id="prov-base-url" value="${baseUrlVal}" placeholder="https://api.openai.com/v1" required autocomplete="off" />
                </div>
                ${apiKeySection}
                <div class="col-12">
                  <label class="form-label required" for="prov-model">Model</label>
                  <div class="d-flex gap-2 mb-2 align-items-center flex-wrap">
                    <button type="button" class="btn btn-outline-secondary btn-sm" id="prov-scan-models-btn">
                      <i class="ri-search-line me-1"></i>Scan Models
                      <span id="prov-scan-spinner" class="spinner-border spinner-border-sm ms-1 d-none" role="status"></span>
                    </button>
                    <span id="prov-scan-status" class="text-muted small"></span>
                  </div>
                  <div id="prov-model-select-wrapper" class="d-none mb-2">
                    <select class="form-select" id="prov-model-select" aria-label="Select discovered model">
                      <option value="">— select a model —</option>
                    </select>
                  </div>
                  <input type="text" class="form-control" id="prov-model" value="${modelVal}" placeholder="e.g. gpt-4o" required autocomplete="off" />
                  <div class="form-text">Type a model name or use Scan Models to discover available models.</div>
                </div>
                <div class="col-md-4">
                  <label class="form-label" for="prov-temperature">Temperature</label>
                  <input type="number" class="form-control" id="prov-temperature" value="${tempVal}" placeholder="Default" step="0.1" min="0" max="2" autocomplete="off" />
                  <div class="form-text">Leave blank for provider default.</div>
                </div>
                <div class="col-md-4">
                  <label class="form-label" for="prov-max-tokens">Max Tokens</label>
                  <input type="number" class="form-control" id="prov-max-tokens" value="${maxTokensVal}" placeholder="4096" min="1" autocomplete="off" />
                </div>
                <div class="col-md-4">
                  <label class="form-label" for="prov-effort">Effort</label>
                  <select class="form-select" id="prov-effort">
                    ${effortOptions}
                  </select>
                </div>
                <div class="col-12">
                  <div class="form-check form-switch">
                    <input class="form-check-input" type="checkbox" role="switch" id="prov-thinking" ${thinkingChecked} />
                    <label class="form-check-label" for="prov-thinking">Enable Thinking / Extended Reasoning</label>
                  </div>
                </div>
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            <button type="button" class="btn btn-primary" id="prov-modal-submit">
              <span id="prov-modal-spinner" class="spinner-border spinner-border-sm me-1 d-none" role="status"></span>
              <i class="ri-save-3-line me-1"></i>${isEdit ? 'Save Changes' : 'Add Provider'}
            </button>
          </div>
        </div>
      </div>
    </div>`
}

function openProviderModal(
  mode: 'add' | 'edit',
  onSuccess: () => Promise<void>,
  provider?: AIProvider
): void {
  removeExistingModals()

  const html = buildProviderModalHtml(mode, provider)
  const wrapper = injectModal(html)
  const modalEl = wrapper.querySelector('#ai-provider-form-modal') as HTMLElement
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const bsModal = new (window as any).bootstrap.Modal(modalEl)

  const isEdit = mode === 'edit'
  const alertEl = modalEl.querySelector('#prov-modal-alert') as HTMLElement
  const submitBtn = modalEl.querySelector('#prov-modal-submit') as HTMLButtonElement
  const spinner = modalEl.querySelector('#prov-modal-spinner') as HTMLElement
  const apiKeyInput = modalEl.querySelector('#prov-api-key') as HTMLInputElement | null
  const apiKeyToggleBtn = modalEl.querySelector('#prov-api-key-toggle') as HTMLButtonElement | null
  const apiKeyToggleIcon = modalEl.querySelector('#prov-api-key-toggle-icon') as HTMLElement | null
  const modelInput = modalEl.querySelector('#prov-model') as HTMLInputElement
  const modelSelectWrapper = modalEl.querySelector('#prov-model-select-wrapper') as HTMLElement
  const modelSelect = modalEl.querySelector('#prov-model-select') as HTMLSelectElement
  const scanBtn = modalEl.querySelector('#prov-scan-models-btn') as HTMLButtonElement
  const scanSpinner = modalEl.querySelector('#prov-scan-spinner') as HTMLElement
  const scanStatus = modalEl.querySelector('#prov-scan-status') as HTMLElement

  // Toggle API key visibility
  if (apiKeyToggleBtn && apiKeyInput && apiKeyToggleIcon) {
    apiKeyToggleBtn.addEventListener('click', () => {
      const isPassword = apiKeyInput.type === 'password'
      apiKeyInput.type = isPassword ? 'text' : 'password'
      apiKeyToggleIcon.className = isPassword ? 'ri-eye-off-line' : 'ri-eye-line'
    })
  }

  // Edit mode: toggle update key section
  if (isEdit) {
    const updateKeyCheck = modalEl.querySelector('#prov-update-key-check') as HTMLInputElement | null
    const apiKeyWrapper = modalEl.querySelector('#prov-api-key-wrapper') as HTMLElement | null
    if (updateKeyCheck && apiKeyWrapper) {
      updateKeyCheck.addEventListener('change', () => {
        if (updateKeyCheck.checked) {
          apiKeyWrapper.classList.remove('d-none')
        } else {
          apiKeyWrapper.classList.add('d-none')
          if (apiKeyInput) apiKeyInput.value = ''
        }
      })
    }
  }

  // Scan models
  scanBtn.addEventListener('click', async () => {
    const protocol = (modalEl.querySelector('#prov-protocol') as HTMLSelectElement).value
    const baseUrl = (modalEl.querySelector('#prov-base-url') as HTMLInputElement).value.trim()

    if (!protocol || !baseUrl) {
      scanStatus.textContent = 'Protocol and Base URL are required to scan models.'
      scanStatus.className = 'text-danger small'
      return
    }

    scanBtn.disabled = true
    scanSpinner.classList.remove('d-none')
    scanStatus.textContent = 'Scanning...'
    scanStatus.className = 'text-muted small'

    try {
      const payload: Parameters<typeof discoverModels>[0] = { protocol, base_url: baseUrl }
      // Include api_key if typed (only available from the current input — not stored)
      if (apiKeyInput && apiKeyInput.value) {
        payload.api_key = apiKeyInput.value
      }
      if (isEdit && provider) {
        payload.provider_id = provider.id
      }

      const result = await discoverModels(payload)
      const models = result.models ?? []

      if (models.length === 0) {
        scanStatus.textContent = 'No models discovered.'
        scanStatus.className = 'text-warning small'
        modelSelectWrapper.classList.add('d-none')
      } else {
        // Populate select
        modelSelect.innerHTML = '<option value="">— select a model —</option>' +
          models.map((m) => `<option value="${escapeAttr(m.id)}">${escapeHtml(m.display_name)}</option>`).join('')
        modelSelectWrapper.classList.remove('d-none')
        scanStatus.textContent = `${models.length} model(s) found.`
        scanStatus.className = 'text-success small'

        // When user picks from dropdown, fill the text input
        modelSelect.addEventListener('change', () => {
          if (modelSelect.value) {
            modelInput.value = modelSelect.value
          }
        })
      }
    } catch (err) {
      scanStatus.textContent = err instanceof Error ? err.message : 'Scan failed.'
      scanStatus.className = 'text-danger small'
      modelSelectWrapper.classList.add('d-none')
    } finally {
      scanBtn.disabled = false
      scanSpinner.classList.add('d-none')
    }
  })

  // Submit
  submitBtn.addEventListener('click', async () => {
    alertEl.classList.add('d-none')

    const label = (modalEl.querySelector('#prov-label') as HTMLInputElement).value.trim()
    const protocol = (modalEl.querySelector('#prov-protocol') as HTMLSelectElement).value
    const baseUrl = (modalEl.querySelector('#prov-base-url') as HTMLInputElement).value.trim()
    const model = modelInput.value.trim()
    const tempRaw = (modalEl.querySelector('#prov-temperature') as HTMLInputElement).value.trim()
    const maxTokensRaw = (modalEl.querySelector('#prov-max-tokens') as HTMLInputElement).value.trim()
    const thinking = (modalEl.querySelector('#prov-thinking') as HTMLInputElement).checked
    const effort = (modalEl.querySelector('#prov-effort') as HTMLSelectElement).value

    const temperature = tempRaw !== '' ? parseFloat(tempRaw) : null
    const maxTokens = maxTokensRaw !== '' ? parseInt(maxTokensRaw, 10) : 4096

    if (!label || !protocol || !baseUrl || !model) {
      alertEl.textContent = 'Label, Protocol, Base URL, and Model are required.'
      alertEl.classList.remove('d-none')
      return
    }

    if (!isEdit) {
      // Create: api_key required
      if (!apiKeyInput || !apiKeyInput.value) {
        alertEl.textContent = 'API Key is required.'
        alertEl.classList.remove('d-none')
        return
      }
    }

    submitBtn.disabled = true
    spinner.classList.remove('d-none')

    try {
      if (isEdit && provider) {
        const updatePayload: Parameters<typeof updateProvider>[1] = {
          revision: provider.revision,
          label,
          protocol,
          base_url: baseUrl,
          model,
          temperature,
          max_tokens: maxTokens,
          thinking,
          effort
        }
        // Only include api_key if the "update key" checkbox was checked and input has value
        const updateKeyCheck = modalEl.querySelector('#prov-update-key-check') as HTMLInputElement | null
        if (updateKeyCheck?.checked && apiKeyInput?.value) {
          updatePayload.api_key = apiKeyInput.value
        }
        await updateProvider(provider.id, updatePayload)
        if (apiKeyInput) apiKeyInput.value = ''
        bsModal.hide()
        showToast('Provider updated successfully.')
        await onSuccess()
      } else {
        await createProvider({
          label,
          protocol,
          base_url: baseUrl,
          api_key: apiKeyInput!.value,
          model,
          temperature,
          max_tokens: maxTokens,
          thinking,
          effort
        })
        if (apiKeyInput) apiKeyInput.value = ''
        bsModal.hide()
        showToast('Provider added successfully.')
        await onSuccess()
      }
    } catch (err) {
      if (
        err instanceof Error &&
        (err as Error & { code?: string }).code === 'revision_conflict'
      ) {
        alertEl.textContent = 'Provider settings have changed. Please close and reload.'
        alertEl.classList.remove('d-none')
        await onSuccess()
      } else if (
        err instanceof Error &&
        (err as Error & { code?: string }).code === 'label_conflict'
      ) {
        alertEl.textContent = 'A provider with this label already exists.'
        alertEl.classList.remove('d-none')
      } else {
        alertEl.textContent = err instanceof Error ? err.message : 'Failed to save provider.'
        alertEl.classList.remove('d-none')
      }
    } finally {
      submitBtn.disabled = false
      spinner.classList.add('d-none')
    }
  })

  // Clear sensitive fields on close
  modalEl.addEventListener('hidden.bs.modal', () => {
    if (apiKeyInput) apiKeyInput.value = ''
    if (apiKeyInput) apiKeyInput.type = 'password'
    if (apiKeyToggleIcon) apiKeyToggleIcon.className = 'ri-eye-line'
    removeExistingModals()
  })

  bsModal.show()
}

// ---------------------------------------------------------------------------
// Reveal API Key Modal
// ---------------------------------------------------------------------------

function openRevealKeyModal(provider: AIProvider): void {
  removeExistingModals()

  const html = `
    <div class="modal fade" id="ai-provider-reveal-modal" tabindex="-1" aria-labelledby="prov-reveal-title" aria-modal="true" role="dialog">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="prov-reveal-title">
              <i class="ri-eye-line me-2"></i>Reveal API Key — ${escapeHtml(provider.label)}
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <div id="prov-reveal-alert" class="alert alert-danger d-none" role="alert"></div>
            <div id="prov-reveal-password-section">
              <p class="text-muted small">Enter your current password to view the API key.</p>
              <div class="mb-3">
                <label class="form-label required" for="prov-reveal-password">Current Password</label>
                <input type="password" class="form-control" id="prov-reveal-password" placeholder="Enter your account password" autocomplete="current-password" />
              </div>
              <button type="button" class="btn btn-primary" id="prov-reveal-submit">
                <span id="prov-reveal-spinner" class="spinner-border spinner-border-sm me-1 d-none" role="status"></span>
                <i class="ri-eye-line me-1"></i>Reveal
              </button>
            </div>
            <div id="prov-reveal-result" class="d-none mt-3">
              <label class="form-label">API Key</label>
              <div class="input-group">
                <input type="text" class="form-control font-monospace" id="prov-reveal-value" readonly aria-label="Revealed API key" />
                <button class="btn btn-outline-secondary" type="button" id="prov-reveal-copy" title="Copy to clipboard">
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
  const modalEl = wrapper.querySelector('#ai-provider-reveal-modal') as HTMLElement
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const bsModal = new (window as any).bootstrap.Modal(modalEl)

  const submitBtn = modalEl.querySelector('#prov-reveal-submit') as HTMLButtonElement
  const spinner = modalEl.querySelector('#prov-reveal-spinner') as HTMLElement
  const alertEl = modalEl.querySelector('#prov-reveal-alert') as HTMLElement
  const passwordSection = modalEl.querySelector('#prov-reveal-password-section') as HTMLElement
  const resultSection = modalEl.querySelector('#prov-reveal-result') as HTMLElement
  const revealValueInput = modalEl.querySelector('#prov-reveal-value') as HTMLInputElement
  const copyBtn = modalEl.querySelector('#prov-reveal-copy') as HTMLButtonElement

  submitBtn.addEventListener('click', async () => {
    const passwordInput = modalEl.querySelector('#prov-reveal-password') as HTMLInputElement
    const currentPassword = passwordInput.value
    alertEl.classList.add('d-none')

    if (!currentPassword) {
      alertEl.textContent = 'Current password is required.'
      alertEl.classList.remove('d-none')
      return
    }

    submitBtn.disabled = true
    spinner.classList.remove('d-none')

    try {
      const result = await revealProviderKey(provider.id, currentPassword)
      // Clear password immediately after call
      passwordInput.value = ''

      // Set plaintext directly in DOM — do not log
      revealValueInput.value = result.api_key
      // Minimise plaintext lifetime in the result object
      Object.assign(result, { api_key: '' })

      passwordSection.classList.add('d-none')
      resultSection.classList.remove('d-none')
    } catch (err) {
      alertEl.textContent = err instanceof Error ? err.message : 'Failed to reveal API key.'
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
      showToast('Failed to copy API key to clipboard.', 'danger')
    }
  })

  // CRITICAL: Clear plaintext from DOM immediately on close
  modalEl.addEventListener('hide.bs.modal', () => {
    revealValueInput.value = ''
    const passwordInput = modalEl.querySelector('#prov-reveal-password') as HTMLInputElement | null
    if (passwordInput) passwordInput.value = ''
  })

  modalEl.addEventListener('hidden.bs.modal', () => {
    removeExistingModals()
  })

  bsModal.show()
}

// ---------------------------------------------------------------------------
// Runtime Status rendering
// ---------------------------------------------------------------------------

async function loadRuntimeStatus(): Promise<void> {
  const statusContainer = document.getElementById('ai-runtime-status')
  const envFallbackContainer = document.getElementById('ai-env-fallback-status')

  if (!statusContainer && !envFallbackContainer) return

  try {
    const status = await getRuntimeStatus()

    if (statusContainer) {
      const chain = status.chain ?? []
      if (chain.length === 0) {
        statusContainer.innerHTML = `
          <span class="text-muted">
            <i class="ri-information-line me-1"></i>No active provider chain configured.
          </span>`
      } else {
        const labels = chain.map((p) =>
          `<span class="badge text-bg-primary me-1">${escapeHtml(p.label)}</span>`
        ).join('')
        statusContainer.innerHTML = `
          <div class="d-flex align-items-center flex-wrap gap-1">
            <i class="ri-links-line me-1 text-muted"></i>
            <span class="text-muted small me-2">Active chain:</span>
            ${labels}
          </div>`
      }
    }

    if (envFallbackContainer) {
      if (status.environment_fallback) {
        const providerName = status.environment_provider
          ? escapeHtml(String(status.environment_provider))
          : 'environment variable'
        envFallbackContainer.innerHTML = `
          <div class="alert alert-info mb-0 py-2 px-3 d-flex align-items-center" role="alert">
            <i class="ri-shield-check-line me-2"></i>
            <div class="small">
              Environment fallback active — using <strong>${providerName}</strong> when no user provider is available.
            </div>
          </div>`
      } else {
        envFallbackContainer.innerHTML = `
          <div class="text-muted small">
            <i class="ri-information-line me-1"></i>No environment fallback configured.
          </div>`
      }
    }
  } catch {
    if (statusContainer) {
      statusContainer.innerHTML = `
        <span class="text-danger small">
          <i class="ri-error-warning-line me-1"></i>Failed to load runtime status.
        </span>`
    }
  }
}

// ---------------------------------------------------------------------------
// Page initialiser — exported entry point
// ---------------------------------------------------------------------------

export async function initAIServicePage(): Promise<void> {
  const container = document.getElementById('ai-providers-list')
  if (!container || container.dataset.inited) return
  container.dataset.inited = 'true'

  // Show loading
  container.innerHTML = `
    <div class="text-center py-4">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Loading...</span>
      </div>
      <p class="text-muted mt-2">Loading providers...</p>
    </div>`

  // Module-level provider cache for action lookups
  let providers: AIProvider[] = []

  const loadProviders = async () => {
    try {
      providers = await listProviders()
      renderProviderList(container, providers)
    } catch (err) {
      container.innerHTML = `
        <div class="alert alert-danger" role="alert">
          <i class="ri-error-warning-line me-2"></i>
          Failed to load providers: ${escapeHtml(err instanceof Error ? err.message : String(err))}
        </div>`
    }
  }

  // Load runtime status in parallel
  loadRuntimeStatus().catch(() => undefined)

  // Wire "Add Provider" button
  const addBtn = document.getElementById('ai-add-provider-btn')
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      openProviderModal('add', loadProviders)
    })
  }

  // Event delegation on the list container
  container.addEventListener('click', async (e) => {
    const target = (e.target as HTMLElement).closest<HTMLElement>('[data-ai-action]')
    if (!target) return

    const action = target.dataset.aiAction
    const providerId = Number(target.dataset.providerId)
    const provider = providers.find((p) => p.id === providerId)

    // toggle-enabled uses the checkbox input directly — handled separately below
    if (action === 'toggle-enabled') return

    if (!provider) return

    if (action === 'edit') {
      openProviderModal('edit', loadProviders, provider)
    } else if (action === 'test') {
      target.classList.add('disabled')
      try {
        const result = await testProvider(provider.id)
        if (result.success) {
          showToast(`${provider.label}: ${result.message}`, 'success')
        } else {
          showToast(`${provider.label}: ${result.message}`, 'danger')
        }
      } catch (err) {
        showToast(err instanceof Error ? err.message : 'Test failed.', 'danger')
      } finally {
        target.classList.remove('disabled')
      }
    } else if (action === 'reveal') {
      openRevealKeyModal(provider)
    } else if (action === 'delete') {
      const providerLabel = target.dataset.providerLabel || provider.label
      if (!window.confirm(`Delete provider "${providerLabel}"? This cannot be undone.`)) return
      target.classList.add('disabled')
      try {
        await deleteProvider(provider.id, provider.revision)
        showToast('Provider deleted.')
        await loadProviders()
      } catch (err) {
        if (!handleRevisionConflict(err, loadProviders)) {
          showToast(err instanceof Error ? err.message : 'Failed to delete provider.', 'danger')
          target.classList.remove('disabled')
        }
      }
    } else if (action === 'move-up') {
      const idx = providers.findIndex((p) => p.id === providerId)
      if (idx <= 0) return
      const newOrder = providers.map((p) => p.id)
      ;[newOrder[idx - 1], newOrder[idx]] = [newOrder[idx], newOrder[idx - 1]]
      // Use max revision across providers as a collective revision stamp
      const revision = Math.max(...providers.map((p) => p.revision))
      try {
        await reorderProviders(newOrder, revision)
        await loadProviders()
      } catch (err) {
        if (!handleRevisionConflict(err, loadProviders)) {
          showToast(err instanceof Error ? err.message : 'Failed to reorder.', 'danger')
        }
      }
    } else if (action === 'move-down') {
      const idx = providers.findIndex((p) => p.id === providerId)
      if (idx < 0 || idx >= providers.length - 1) return
      const newOrder = providers.map((p) => p.id)
      ;[newOrder[idx], newOrder[idx + 1]] = [newOrder[idx + 1], newOrder[idx]]
      const revision = Math.max(...providers.map((p) => p.revision))
      try {
        await reorderProviders(newOrder, revision)
        await loadProviders()
      } catch (err) {
        if (!handleRevisionConflict(err, loadProviders)) {
          showToast(err instanceof Error ? err.message : 'Failed to reorder.', 'danger')
        }
      }
    }
  })

  // Handle enabled toggle (change event on checkboxes)
  container.addEventListener('change', async (e) => {
    const target = e.target as HTMLElement
    if (
      target.tagName !== 'INPUT' ||
      (target as HTMLInputElement).type !== 'checkbox' ||
      target.dataset.aiAction !== 'toggle-enabled'
    ) {
      return
    }

    const checkbox = target as HTMLInputElement
    const providerId = Number(checkbox.dataset.providerId)
    const provider = providers.find((p) => p.id === providerId)
    if (!provider) return

    const newEnabled = checkbox.checked
    checkbox.disabled = true

    try {
      await setProviderEnabled(providerId, newEnabled)
      provider.enabled = newEnabled
      showToast(`${provider.label} ${newEnabled ? 'enabled' : 'disabled'}.`)
      // Reload to refresh runtime status too
      await loadProviders()
      loadRuntimeStatus().catch(() => undefined)
    } catch (err) {
      // Revert checkbox on failure
      checkbox.checked = !newEnabled
      showToast(err instanceof Error ? err.message : 'Failed to update.', 'danger')
    } finally {
      checkbox.disabled = false
    }
  })

  await loadProviders()
}
