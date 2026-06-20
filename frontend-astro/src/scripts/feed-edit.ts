import { api } from './api'
import type { Site, FilterConfig } from './api'
import { escapeHtml, escapeAttr } from '@/scripts/utils'
import {
  renderPreview,
  showLoading,
  showError,
  clearPreview,
  showDebugBanner
} from './preview-table'
import {
  initFilterBuilder,
  getFilterConfig,
  createDefaultFilterConfig
} from './filter-builder'

// ---------------------------------------------------------------------------
// CodeMirror minimal interface (loaded as global script, not typed package)
// ---------------------------------------------------------------------------
interface CodeMirrorEditor {
  getValue(): string
  setValue(value: string): void
  refresh(): void
  on(event: string, handler: () => void): void
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
interface EditData {
  name: string
  url: string
  refresh_frequency: number
  list_rules: string
  content_rules: string
  filter_rules: string
  sample_url: string
}

let sites: Site[] = []
let selectedSite: Site | null = null
let editData: EditData = emptyEditData()
let debugMode = false
let rulesExpanded = true
let crawlingId: number | null = null
let saving = false

function emptyEditData(): EditData {
  return {
    name: '',
    url: '',
    refresh_frequency: 60,
    list_rules: '',
    content_rules: '',
    filter_rules: '',
    sample_url: ''
  }
}

// ---------------------------------------------------------------------------
// DOM references (resolved once on init)
// ---------------------------------------------------------------------------
let tableBody: HTMLElement
let tableLoading: HTMLElement
let refreshBtn: HTMLButtonElement
let editorSection: HTMLElement
let editorTitle: HTMLElement
let inputUrl: HTMLInputElement
let inputName: HTMLInputElement
let inputFreq: HTMLInputElement
let inputSampleUrl: HTMLInputElement
let cmListRulesEl: HTMLElement
let cmContentRulesEl: HTMLElement
let cmListRules: CodeMirrorEditor | null = null
let cmContentRules: CodeMirrorEditor | null = null
let rulesPanel: HTMLElement
let toggleRulesBtn: HTMLButtonElement
let saveBtn: HTMLButtonElement
let crawlEditorBtn: HTMLButtonElement
let debugCheckbox: HTMLInputElement
let debugLabel: HTMLElement
let analyzeListBtn: HTMLButtonElement
let analyzeContentBtn: HTMLButtonElement
let testListBtn: HTMLButtonElement
let testContentBtn: HTMLButtonElement
let previewSection: HTMLElement
let previewBody: HTMLElement
let testBothBtn: HTMLButtonElement
let filterBuilderRoot: HTMLElement
let filterPreviewBtn: HTMLButtonElement

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function $(selector: string): HTMLElement {
  return document.querySelector(selector) as HTMLElement
}

function parseSafeJson(str: string): Record<string, unknown> {
  try {
    return JSON.parse(str)
  } catch {
    return {}
  }
}

function getSiteIdFromUrl(): number | null {
  const params = new URLSearchParams(window.location.search)
  const id = params.get('site') || params.get('id')
  return id ? parseInt(id, 10) : null
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

export function initFeedEdit(): void {
  const root = document.getElementById('feed-edit-root')
  if (!root || root.dataset.inited) return
  root.dataset.inited = 'true'

  // Resolve DOM refs
  tableBody = $('#feed-table-body')
  tableLoading = $('#feed-table-loading')
  refreshBtn = $('#btn-refresh-table') as HTMLButtonElement
  editorSection = $('#editor-section')
  editorTitle = $('#editor-title')
  inputUrl = $('#input-url') as HTMLInputElement
  inputName = $('#input-name') as HTMLInputElement
  inputFreq = $('#input-freq') as HTMLInputElement
  inputSampleUrl = $('#input-sample-url') as HTMLInputElement
  cmListRulesEl = $('#cm-list-rules')
  cmContentRulesEl = $('#cm-content-rules')
  rulesPanel = $('#rules-panel')
  toggleRulesBtn = $('#btn-toggle-rules') as HTMLButtonElement
  saveBtn = $('#btn-save') as HTMLButtonElement
  crawlEditorBtn = $('#btn-crawl-editor') as HTMLButtonElement
  debugCheckbox = $('#debug-checkbox') as HTMLInputElement
  debugLabel = $('#debug-label')
  analyzeListBtn = $('#btn-analyze-list') as HTMLButtonElement
  analyzeContentBtn = $('#btn-analyze-content') as HTMLButtonElement
  testListBtn = $('#btn-test-list') as HTMLButtonElement
  testContentBtn = $('#btn-test-content') as HTMLButtonElement
  previewSection = $('#preview-section')
  previewBody = $('#preview-body')
  testBothBtn = $('#btn-test-both') as HTMLButtonElement
  filterBuilderRoot = $('#filter-builder-root')
  filterPreviewBtn = $('#btn-filter-preview') as HTMLButtonElement

  // Bind events
  refreshBtn.addEventListener('click', fetchSites)

  inputUrl.addEventListener('input', () => {
    editData.url = inputUrl.value
  })
  inputName.addEventListener('input', () => {
    editData.name = inputName.value
  })
  inputFreq.addEventListener('input', () => {
    editData.refresh_frequency = parseInt(inputFreq.value, 10) || 60
  })
  inputSampleUrl.addEventListener('input', () => {
    editData.sample_url = inputSampleUrl.value
  })
  const CM = (window as unknown as Record<string, unknown>).CodeMirror as
    | ((el: HTMLElement, opts: Record<string, unknown>) => CodeMirrorEditor)
    | undefined
  if (CM) {
    const cmOpts = {
      mode: { name: 'javascript', json: true },
      theme: 'default',
      lineNumbers: true,
      lineWrapping: true,
      tabSize: 2,
      indentWithTabs: false,
      matchBrackets: true,
      readOnly: false
    }
    cmListRules = CM(cmListRulesEl, { ...cmOpts, value: '' })
    cmContentRules = CM(cmContentRulesEl, { ...cmOpts, value: '' })
    cmListRules.on('change', () => { editData.list_rules = cmListRules!.getValue() })
    cmContentRules.on('change', () => { editData.content_rules = cmContentRules!.getValue() })
  }

  toggleRulesBtn.addEventListener('click', handleToggleRules)
  saveBtn.addEventListener('click', handleSave)
  crawlEditorBtn.addEventListener('click', () => {
    if (selectedSite) handleManualCrawl(selectedSite.id)
  })
  debugCheckbox.addEventListener('change', () => {
    debugMode = debugCheckbox.checked
    updateDebugUI()
  })
  analyzeListBtn.addEventListener('click', () => handleAnalyze('list'))
  analyzeContentBtn.addEventListener('click', () => handleAnalyze('content'))
  testListBtn.addEventListener('click', () => handleTest('list'))
  testContentBtn.addEventListener('click', () =>
    handleTest('content', editData.sample_url)
  )
  testBothBtn.addEventListener('click', () => handleTest('both'))

  filterPreviewBtn.addEventListener('click', () => {
    filterPreviewBtn.classList.toggle('active')
    const isActive = filterPreviewBtn.classList.contains('active')
    filterPreviewBtn.className = isActive
      ? 'btn btn-sm btn-secondary active'
      : 'btn btn-sm btn-outline-secondary'
  })

  // Initial data load
  fetchSites().then(() => {
    const autoId = getSiteIdFromUrl()
    if (autoId) handleEdit(autoId)
  })
}

// ---------------------------------------------------------------------------
// Fetch & render table
// ---------------------------------------------------------------------------

async function fetchSites(): Promise<void> {
  tableLoading.classList.remove('d-none')
  tableBody.innerHTML = ''
  refreshBtn.disabled = true

  try {
    sites = await api.getSites()
    renderTable()
  } catch (err: unknown) {
    console.error(err)
  } finally {
    tableLoading.classList.add('d-none')
    refreshBtn.disabled = false
  }
}

function renderTable(): void {
  tableBody.innerHTML = ''

  if (sites.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="4" class="text-center text-muted py-4">No feeds found.</td>
      </tr>`
    return
  }

  for (const site of sites) {
    const tr = document.createElement('tr')
    if (selectedSite?.id === site.id) {
      tr.classList.add('table-active')
    }
    tr.dataset.siteId = String(site.id)

    const freq = site.refresh_frequency || 60
    const freqDisplay = freq >= 60 ? `${Math.round(freq / 60 * 10) / 10}h` : `${freq}min`
    tr.innerHTML = `
      <td class="fw-medium">${escapeHtml(site.name)}</td>
      <td class="text-truncate" style="max-width:250px">
        <a href="${escapeAttr(site.url)}" target="_blank" rel="noreferrer" class="text-decoration-none text-body">
          ${escapeHtml(site.url)} <i class="ri-external-link-line ms-1 small"></i>
        </a>
      </td>
      <td>${freqDisplay}</td>
      <td>
        <div class="d-flex gap-1">
          <button class="btn btn-sm btn-outline-primary btn-action" data-action="edit" title="Edit Details">
            <i class="ri-pencil-line"></i>
          </button>
          <button class="btn btn-sm btn-outline-secondary btn-action" data-action="duplicate" title="Duplicate">
            <i class="ri-file-copy-line"></i>
          </button>
          <button class="btn btn-sm btn-outline-success btn-action" data-action="crawl" title="Trigger Crawl">
            <i class="ri-play-line"></i>
          </button>
          <button class="btn btn-sm btn-outline-danger btn-action" data-action="delete" title="Delete">
            <i class="ri-delete-bin-line"></i>
          </button>
        </div>
      </td>`

    // Bind row action buttons
    tr.querySelectorAll<HTMLButtonElement>('.btn-action').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation()
        const action = btn.dataset.action
        if (action === 'edit') handleEdit(site.id)
        else if (action === 'duplicate') handleDuplicate(site.id)
        else if (action === 'crawl') handleManualCrawl(site.id, btn)
        else if (action === 'delete') handleDelete(site.id)
      })
    })

    tableBody.appendChild(tr)
  }
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

async function handleEdit(id: number): Promise<void> {
  try {
    const site = await api.getSite(id)
    selectedSite = site
    const filterConfig = site.filter_rules ?? null
    editData = {
      name: site.name,
      url: site.url,
      refresh_frequency: site.refresh_frequency || 60,
      list_rules: JSON.stringify(site.list_rules, null, 2),
      content_rules: JSON.stringify(site.content_rules, null, 2),
      filter_rules: filterConfig ? JSON.stringify(filterConfig) : '',
      sample_url: ''
    }

    // Populate form
    inputUrl.value = editData.url
    inputName.value = editData.name
    inputFreq.value = String(editData.refresh_frequency)
    inputSampleUrl.value = ''
    if (cmListRules) cmListRules.setValue(editData.list_rules)
    if (cmContentRules) cmContentRules.setValue(editData.content_rules)
    setTimeout(() => { cmListRules?.refresh(); cmContentRules?.refresh() }, 0)

    // Initialize filter builder (always visible)
    initFilterBuilder(filterBuilderRoot, filterConfig ?? createDefaultFilterConfig())
    filterPreviewBtn.classList.remove('active')
    filterPreviewBtn.className = 'btn btn-sm btn-outline-secondary'

    editorTitle.textContent = `Editing: ${site.name}`
    editorSection.classList.remove('d-none')
    previewSection.classList.remove('d-none')
    clearPreview(previewBody)

    // Highlight active row
    renderTable()

    // Smooth scroll
    setTimeout(() => {
      editorSection.scrollIntoView({ behavior: 'smooth' })
    }, 100)
  } catch (err: unknown) {
    alert('Error fetching site details: ' + (err as Error).message)
  }
}

async function handleDuplicate(id: number): Promise<void> {
  if (!window.confirm('Duplicate this feed configuration?')) return
  try {
    await api.duplicateSite(id)
    await fetchSites()
  } catch (err: unknown) {
    alert('Duplicate failed: ' + (err as Error).message)
  }
}

async function handleDelete(id: number): Promise<void> {
  if (!window.confirm('Are you sure you want to delete this feed?')) return
  try {
    await api.deleteSite(id)
    if (selectedSite?.id === id) {
      selectedSite = null
      editorSection.classList.add('d-none')
      previewSection.classList.add('d-none')
    }
    await fetchSites()
  } catch (err: unknown) {
    alert('Delete failed: ' + (err as Error).message)
  }
}

async function handleManualCrawl(
  id: number,
  btn?: HTMLButtonElement
): Promise<void> {
  if (crawlingId === id) return
  crawlingId = id

  // Show spinner on the specific button
  const targetBtn =
    btn ||
    (tableBody.querySelector(
      `tr[data-site-id="${id}"] [data-action="crawl"]`
    ) as HTMLButtonElement | null)

  let originalHtml = ''
  if (targetBtn) {
    originalHtml = targetBtn.innerHTML
    targetBtn.innerHTML =
      '<span class="spinner-border spinner-border-sm" role="status"></span>'
    targetBtn.disabled = true
  }

  try {
    await api.triggerCrawl(id, debugMode)
    alert('Crawl task triggered successfully!')
  } catch (err: unknown) {
    alert('Crawl failed: ' + (err as Error).message)
  } finally {
    crawlingId = null
    if (targetBtn) {
      targetBtn.innerHTML = originalHtml
      targetBtn.disabled = false
    }
  }
}

async function handleSave(): Promise<void> {
  if (!selectedSite || saving) return

  // Validate JSON
  let listRules: unknown
  let contentRules: unknown
  try {
    listRules = JSON.parse(editData.list_rules)
  } catch {
    alert('Invalid JSON in List Rules.')
    return
  }
  try {
    contentRules = JSON.parse(editData.content_rules)
  } catch {
    alert('Invalid JSON in Content Rules.')
    return
  }

  saving = true
  saveBtn.disabled = true
  saveBtn.innerHTML =
    '<span class="spinner-border spinner-border-sm" role="status"></span> Updating...'

  const filterConfig: FilterConfig | null = getFilterConfig()

  try {
    await api.updateSite(selectedSite.id, {
      name: editData.name,
      url: editData.url,
      refresh_frequency: editData.refresh_frequency,
      list_rules: listRules as Record<string, unknown>,
      content_rules: contentRules as Record<string, unknown>,
      filter_rules: filterConfig
    })
    alert('Site updated successfully!')
    await fetchSites()
  } catch (err: unknown) {
    alert('Update failed: ' + (err as Error).message)
  } finally {
    saving = false
    saveBtn.disabled = false
    saveBtn.innerHTML = '<i class="ri-save-line me-1"></i> Save Changes'
  }
}

async function handleAnalyze(mode: 'list' | 'content'): Promise<void> {
  let targetUrl: string | null
  if (mode === 'list') {
    targetUrl = editData.url
  } else {
    targetUrl =
      editData.sample_url ||
      window.prompt('Enter sample article URL for analysis:')
  }
  if (!targetUrl) return

  const btn = mode === 'list' ? analyzeListBtn : analyzeContentBtn
  const originalHtml = btn.innerHTML
  btn.disabled = true
  btn.innerHTML =
    '<span class="spinner-border spinner-border-sm" role="status"></span> Analyzing...'

  try {
    const method = mode === 'list' ? api.analyzeList : api.analyzeContent
    const data = await method(targetUrl, debugMode)
    const rulesJson = typeof data.rules === 'string'
      ? data.rules
      : JSON.stringify(data.rules, null, 2)

    if (mode === 'list') {
      editData.list_rules = rulesJson
      if (cmListRules) cmListRules.setValue(rulesJson)
    } else {
      editData.content_rules = rulesJson
      if (cmContentRules) cmContentRules.setValue(rulesJson)
    }

    if (debugMode && data.debug_dir) {
      setTimeout(() => alert('Debug artifacts: ' + data.debug_dir), 500)
    }
  } catch (err: unknown) {
    alert('AI Analysis failed: ' + (err as Error).message)
  } finally {
    btn.disabled = false
    btn.innerHTML = originalHtml
  }
}

async function handleTest(
  mode: string,
  customUrl?: string
): Promise<void> {
  const targetUrl = customUrl || editData.url

  if (mode === 'list' && !targetUrl) {
    showError(previewBody, 'Please enter a Target URL first.')
    return
  }
  if (mode === 'content' && !targetUrl) {
    showError(
      previewBody,
      'Please enter a Sample URL to test content extraction.'
    )
    return
  }

  showLoading(previewBody, mode)
  previewSection.scrollIntoView({ behavior: 'smooth', block: 'start' })

  const previewFilterConfig = filterPreviewBtn.classList.contains('active') ? getFilterConfig() : null

  try {
    const payload = {
      url: targetUrl,
      list_rules: parseSafeJson(editData.list_rules),
      content_rules: parseSafeJson(editData.content_rules),
      filter_rules: previewFilterConfig,
      mode,
      target_url: customUrl || undefined
    }

    const res = await api.previewCrawl(payload, debugMode)
    if (res.status === 'success') {
      const first = res.data?.[0] as unknown as Record<string, unknown> | undefined
      if (first && 'error' in first && typeof first.error === 'string') {
        showError(previewBody, first.error)
      } else {
        // Build set of filtered article URLs for visual indicators
        const filteredUrls = new Set<string>(
          res.data
            .filter((item) => item.filtered)
            .map((item) => item.url ?? '')
            .filter(Boolean)
        )
        renderPreview(previewBody, res.data, mode, filteredUrls.size > 0 ? filteredUrls : undefined, res.filter_summary)
        if (debugMode && res.debug_dir) {
          showDebugBanner(previewBody, res.debug_dir)
        }
      }
    }
  } catch (err: unknown) {
    showError(previewBody, (err as Error).message || 'Preview failed')
  }
}

function handleToggleRules(): void {
  rulesExpanded = !rulesExpanded
  if (rulesExpanded) {
    rulesPanel.classList.remove('d-none')
    toggleRulesBtn.innerHTML =
      '<i class="ri-code-line me-1"></i> Hide Rules'
    setTimeout(() => { cmListRules?.refresh(); cmContentRules?.refresh() }, 10)
  } else {
    rulesPanel.classList.add('d-none')
    toggleRulesBtn.innerHTML =
      '<i class="ri-code-line me-1"></i> Show Rules'
  }
}

function updateDebugUI(): void {
  const color = debugMode ? 'text-warning' : 'text-muted'
  debugLabel.className = `d-flex align-items-center gap-1 ${color}`
}

