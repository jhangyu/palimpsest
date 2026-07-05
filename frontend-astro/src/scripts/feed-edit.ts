/*
---
name: feed-edit
description: "Feed edit page: split-panel UI to select a site, edit crawl rules in CodeMirror, configure article filters, run AI analysis, preview crawl results, and save site changes"
type: script
target:
  layer: frontend
  domain: feed
spec_doc: null
test_file: tests/stage2/e2e/stage2/feeds.spec.ts
functions:
  - name: emptyEditData
    line: 83
    purpose: "Return a blank EditData object with default field values"
  - name: getSiteIdFromUrl
    line: 143
    purpose: "Parse site ID from URL query params (?site= or ?id=)"
  - name: initFeedEdit
    line: 153
    purpose: "Page entry point: resolve DOM refs, bind all event handlers, and load initial site list"
  - name: fetchSites
    line: 257
    purpose: "Reload sites from API bypassing cache and re-render the selection table"
  - name: renderTable
    line: 274
    purpose: "Render the site selection table with action buttons for each row"
  - name: handleEdit
    line: 339
    purpose: "Load site details and populate the editor form and CodeMirror editors"
  - name: handleDuplicate
    line: 391
    purpose: "Duplicate a site configuration via API and refresh the table"
  - name: handleDelete
    line: 401
    purpose: "Delete a site after confirmation; clear editor if the deleted site was selected"
  - name: handleManualCrawl
    line: 416
    purpose: "Trigger an immediate crawl for a site with spinner feedback on the action button"
  - name: handleSave
    line: 452
    purpose: "Validate JSON rules and filter config, then save site edits via API"
  - name: handleAnalyze
    line: 498
    purpose: "Invoke AI analysis for list or content rules and populate the CodeMirror editor"
  - name: handleTest
    line: 544
    purpose: "Preview crawl with current rules and render results in the preview section"
  - name: handleToggleRules
    line: 601
    purpose: "Toggle visibility of the rules panel and refresh CodeMirror editor instances"
  - name: updateDebugUI
    line: 615
    purpose: "Update debug label color based on debug mode state"
---
*/
import { api } from './api'
import type { Site, FilterConfig, RefreshFrequencyMode } from './api'
import { invalidateCache } from '@/scripts/cache'
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
import {
  parseSafe,
  applySourceTypeUi,
  initCodeMirror,
  type CodeMirrorEditor,
  type SourceTypeState,
  type SourceTypeElements
} from './feed-rules-core'

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
interface EditData {
  name: string
  url: string
  refresh_frequency: number
  refresh_frequency_mode: RefreshFrequencyMode
  list_rules: string
  content_rules: string
  filter_rules: string
  sample_url: string
  source_type: 'html' | 'rss'
  rss_full_content: boolean
}

let sites: Site[] = []
let selectedSite: Site | null = null
let editData: EditData = emptyEditData()
let debugMode = false
let rulesExpanded = true
let crawlingId: number | null = null
let saving = false
let rssHasFullContent = false

function emptyEditData(): EditData {
  return {
    name: '',
    url: '',
    refresh_frequency: 60,
    refresh_frequency_mode: 'auto',
    list_rules: '',
    content_rules: '',
    filter_rules: '',
    sample_url: '',
    source_type: 'html',
    rss_full_content: false
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
let inputFreqMode: HTMLSelectElement
let manualFreqWrapper: HTMLElement
let autoFreqStatus: HTMLElement
let inputSampleUrl: HTMLInputElement
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
let forceRefreshBtn: HTMLButtonElement
let forceRefreshConfirmBtn: HTMLButtonElement
let sourceTypeHtml: HTMLButtonElement
let sourceTypeRss: HTMLButtonElement
let rssFullContentWrapper: HTMLElement
let rssFullContentCheck: HTMLInputElement
let rssFullContentInfo: HTMLElement
let listRulesSection: HTMLElement
let contentRulesSection: HTMLElement

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function $(selector: string): HTMLElement {
  return document.querySelector(selector) as HTMLElement
}

function getSiteIdFromUrl(): number | null {
  const params = new URLSearchParams(window.location.search)
  const id = params.get('site') || params.get('id')
  return id ? parseInt(id, 10) : null
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')
}

function formatMinutes(minutes: number): string {
  if (minutes >= 1440) return `${formatNumber(minutes / 1440)}d`
  if (minutes >= 60) return `${formatNumber(minutes / 60)}h`
  return `${formatNumber(minutes)}min`
}

function formatHoursMins(minutes: number): string {
  if (minutes >= 60) {
    const hrs = Math.floor(minutes / 60)
    const mins = (minutes % 60).toFixed(2)
    return `${hrs}hr ${mins}min`
  }
  return `${minutes.toFixed(2)}min`
}

function getAutoFrequencyMinutes(site: Site): number | null {
  return site.auto_refresh_frequency_minutes ?? null
}

function formatRefreshDisplay(site: Site): string {
  const mode = site.refresh_frequency_mode ?? 'manual'
  if (mode === 'auto') {
    const autoMinutes = getAutoFrequencyMinutes(site)
    return autoMinutes ? `Auto ${formatHoursMins(autoMinutes)}` : 'Auto pending'
  }
  return formatMinutes(site.refresh_frequency || 60)
}

function formatAutoStatus(site: Site): string {
  const autoMinutes = getAutoFrequencyMinutes(site)
  const parts = [autoMinutes ? `Auto currently estimates ${formatHoursMins(autoMinutes)} between crawls.` : 'Auto frequency is pending until enough crawl data is available.']
  if (site.last_crawled_at) parts.push(`Last crawled: ${new Date(site.last_crawled_at).toLocaleString()}.`)
  if (site.next_crawl_at) parts.push(`Next crawl: ${new Date(site.next_crawl_at).toLocaleString()}.`)
  return parts.join(' ')
}

function updateRefreshFrequencyUi(): void {
  const isAuto = editData.refresh_frequency_mode === 'auto'
  inputFreqMode.value = editData.refresh_frequency_mode
  manualFreqWrapper.classList.toggle('d-none', isAuto)
  autoFreqStatus.classList.toggle('d-none', !isAuto)
  inputFreq.disabled = isAuto
  if (isAuto && selectedSite) {
    autoFreqStatus.textContent = formatAutoStatus(selectedSite)
  } else if (isAuto) {
    autoFreqStatus.textContent = 'Auto frequency is pending until enough crawl data is available.'
  } else {
    autoFreqStatus.textContent = ''
  }
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
  inputFreqMode = $('#input-freq-mode') as HTMLSelectElement
  manualFreqWrapper = $('#manual-freq-wrapper')
  autoFreqStatus = $('#auto-freq-status')
  inputSampleUrl = $('#input-sample-url') as HTMLInputElement
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
  forceRefreshBtn = $('#btn-force-refresh') as HTMLButtonElement
  forceRefreshConfirmBtn = $('#btn-force-refresh-confirm') as HTMLButtonElement
  sourceTypeHtml = $('#source-type-html') as HTMLButtonElement
  sourceTypeRss = $('#source-type-rss') as HTMLButtonElement
  rssFullContentWrapper = $('#rss-full-content-wrapper') as HTMLElement
  rssFullContentCheck = $('#rss-full-content-check') as HTMLInputElement
  rssFullContentInfo = $('#rss-full-content-info') as HTMLElement
  listRulesSection = $('#list-rules-section') as HTMLElement
  contentRulesSection = $('#content-rules-section') as HTMLElement

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
  inputFreqMode.addEventListener('change', () => {
    editData.refresh_frequency_mode = inputFreqMode.value === 'manual' ? 'manual' : 'auto'
    updateRefreshFrequencyUi()
  })
  inputSampleUrl.addEventListener('input', () => {
    editData.sample_url = inputSampleUrl.value
  })
  cmListRules = initCodeMirror('cm-list-rules', '')
  cmContentRules = initCodeMirror('cm-content-rules', '')
  cmListRules?.on('change', () => { editData.list_rules = cmListRules!.getValue() })
  cmContentRules?.on('change', () => { editData.content_rules = cmContentRules!.getValue() })

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
  testListBtn.addEventListener('click', async () => {
    if (editData.source_type === 'rss') {
      if (!editData.url) {
        showError(previewBody, 'Please enter a Target URL first.')
        return
      }
      previewSection.classList.remove('d-none')
      showLoading(previewBody, 'list')
      previewSection.scrollIntoView({ behavior: 'smooth', block: 'start' })
      try {
        const result = await api.parseFeed(editData.url)
        renderPreview(previewBody, result.items.map(item => ({
          title: item.title,
          url: item.url,
          published_at: item.pub_date
        })), 'list')
        rssHasFullContent = result.has_full_content
        if (rssHasFullContent && rssFullContentInfo) {
          rssFullContentInfo.textContent = `Feed contains full article content (${result.item_count} items)`
          rssFullContentInfo.style.display = ''
        }
        callApplySourceTypeUi()
      } catch (e: unknown) {
        showError(previewBody, (e instanceof Error ? e.message : 'Failed to parse RSS feed'))
      }
    } else {
      handleTest('list')
    }
  })
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

  // Force Refresh button → show scope selection modal
  forceRefreshBtn?.addEventListener('click', () => {
    if (!selectedSite) return
    // Reset radio to default
    const scopeCurrentRadio = document.getElementById('scopeCurrent') as HTMLInputElement | null
    if (scopeCurrentRadio) scopeCurrentRadio.checked = true
    const modalEl = document.getElementById('forceRefreshModal')
    if (!modalEl) return
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const modal = (window as any).bootstrap.Modal.getOrCreateInstance(modalEl)
    modal.show()
  })

  // Force Refresh modal confirm → call API
  forceRefreshConfirmBtn?.addEventListener('click', () => {
    if (!selectedSite) return
    if (forceRefreshConfirmBtn) forceRefreshConfirmBtn.disabled = true
    const scopeInput = document.querySelector('input[name="forceRefreshScope"]:checked') as HTMLInputElement | null
    const scope = (scopeInput?.value as 'current' | 'all_db') || 'current'
    const modalEl = document.getElementById('forceRefreshModal')
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    if (modalEl) (window as any).bootstrap.Modal.getOrCreateInstance(modalEl).hide()
    handleForceRefresh(selectedSite.id, scope)
  })

  // HTML/RSS toggle handlers
  sourceTypeHtml?.addEventListener('click', () => {
    editData.source_type = 'html'
    editData.rss_full_content = false
    if (rssFullContentCheck) rssFullContentCheck.checked = false
    rssHasFullContent = false
    callApplySourceTypeUi()
  })

  sourceTypeRss?.addEventListener('click', () => {
    editData.source_type = 'rss'
    callApplySourceTypeUi()
  })

  rssFullContentCheck?.addEventListener('change', () => {
    editData.rss_full_content = rssFullContentCheck.checked
    callApplySourceTypeUi()
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
    invalidateCache('sites') // Force fresh fetch — bypasses module-level cache
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

    const freqDisplay = formatRefreshDisplay(site)
    const typeBadge = site.source_type === 'rss'
      ? ' <span class="badge bg-warning text-dark ms-1" style="font-size:0.7em">RSS</span>'
      : ''
    tr.innerHTML = `
      <td class="fw-medium">${escapeHtml(site.name)}${typeBadge}</td>
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
    // Handle list_rules/content_rules: the API may return them as string (TEXT column)
    // or as object (JSON column). Normalize to a formatted JSON string for the editor.
    const normalizeRules = (rules: unknown): string => {
      if (typeof rules === 'string') return rules  // already a JSON string
      return JSON.stringify(rules, null, 2)
    }
    editData = {
      name: site.name,
      url: site.url,
      refresh_frequency: site.refresh_frequency || 60,
      refresh_frequency_mode: site.refresh_frequency_mode ?? 'manual',
      list_rules: normalizeRules(site.list_rules),
      content_rules: normalizeRules(site.content_rules),
      filter_rules: filterConfig ? JSON.stringify(filterConfig) : '',
      sample_url: '',
      source_type: site.source_type || 'html',
      rss_full_content: site.rss_full_content || false
    }

    // Populate RSS UI state
    if (rssFullContentCheck) rssFullContentCheck.checked = editData.rss_full_content
    rssHasFullContent = editData.rss_full_content // assume full content if it was saved that way
    callApplySourceTypeUi()

    // Populate form
    inputUrl.value = editData.url
    inputName.value = editData.name
    inputFreq.value = String(editData.refresh_frequency)
    updateRefreshFrequencyUi()
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

async function handleForceRefresh(
  siteId: number,
  scope: 'current' | 'all_db'
): Promise<void> {
  forceRefreshBtn.disabled = true
  const originalHtml = forceRefreshBtn.innerHTML
  forceRefreshBtn.innerHTML =
    '<span class="spinner-border spinner-border-sm" role="status"></span>'

  try {
    await api.forceRefresh(siteId, scope)
    alert('Force refresh started. Articles will be re-crawled in the background.')
  } catch (err: unknown) {
    alert('Force refresh failed: ' + (err as Error).message)
  } finally {
    forceRefreshBtn.innerHTML = originalHtml
    forceRefreshBtn.disabled = false
    if (forceRefreshConfirmBtn) forceRefreshConfirmBtn.disabled = false
  }
}

async function handleSave(): Promise<void> {
  if (!selectedSite || saving) return

  // Validate JSON — skip for RSS mode
  let listRules: unknown
  let contentRules: unknown
  if (editData.source_type === 'rss') {
    listRules = {}
  } else {
    try {
      listRules = JSON.parse(editData.list_rules)
    } catch {
      alert('Invalid JSON in List Rules.')
      return
    }
  }
  if (editData.source_type === 'rss' && editData.rss_full_content) {
    contentRules = {}
  } else {
    try {
      contentRules = JSON.parse(editData.content_rules)
    } catch {
      alert('Invalid JSON in Content Rules.')
      return
    }
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
      refresh_frequency: editData.refresh_frequency || 60,
      refresh_frequency_mode: editData.refresh_frequency_mode,
      list_rules: listRules as Record<string, unknown>,
      content_rules: contentRules as Record<string, unknown>,
      filter_rules: filterConfig,
      source_type: editData.source_type,
      rss_full_content: editData.rss_full_content
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
  const otherBtn = mode === 'list' ? analyzeContentBtn : analyzeListBtn
  const originalHtml = btn.innerHTML
  btn.disabled = true
  if (otherBtn) otherBtn.disabled = true
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
    if (otherBtn) otherBtn.disabled = false
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
      list_rules: parseSafe(editData.list_rules),
      content_rules: parseSafe(editData.content_rules),
      filter_rules: previewFilterConfig,
      mode,
      target_url: customUrl || undefined,
      source_type: editData.source_type
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

function callApplySourceTypeUi(): void {
  const state: SourceTypeState = {
    sourceType: editData.source_type as 'html' | 'rss',
    rssFullContent: editData.rss_full_content,
    rssHasFullContent: rssHasFullContent
  }
  const els: SourceTypeElements = {
    sourceTypeHtml,
    sourceTypeRss,
    listRulesSection,
    contentRulesSection,
    analyzeListBtn,
    testListBtn,
    testBothBtn,
    rssFullContentWrapper
  }
  applySourceTypeUi(state, els)
}

function handleToggleRules(): void {
  rulesExpanded = !rulesExpanded
  if (rulesExpanded) {
    rulesPanel.classList.remove('d-none')
    toggleRulesBtn.innerHTML =
      '<i class="ri-code-line me-1"></i> Hide Rules JSON'
    setTimeout(() => { cmListRules?.refresh(); cmContentRules?.refresh() }, 10)
  } else {
    rulesPanel.classList.add('d-none')
    toggleRulesBtn.innerHTML =
      '<i class="ri-code-line me-1"></i> Show Rules JSON'
  }
}

function updateDebugUI(): void {
  const color = debugMode ? 'text-warning' : 'text-muted'
  debugLabel.className = `d-flex align-items-center gap-1 ${color}`
}

