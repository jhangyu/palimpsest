/*
---
name: feed-wizard
description: "Feed creation wizard: AI-analyze list and content URLs, preview crawl results via CodeMirror, and save a new site with validated JSON rules"
type: script
target:
  layer: frontend
  domain: feed
spec_doc: null
test_file: tests/stage2/e2e/stage2/feeds.spec.ts
functions:
  - name: renderPreviewTable
    line: 34
    purpose: "Render crawl preview items into a Bootstrap striped table with title, URL/time, and content"
  - name: initFeedWizard
    line: 84
    purpose: "Page entry point: wire analyze, test, toggle-rules, and save buttons with CodeMirror editors"
---
*/
import { api } from '@/scripts/api'
import type { PreviewItem, PreviewCrawlPayload } from '@/scripts/api'
import { escapeHtml, escapeAttr } from '@/scripts/utils'
import { parseSafe, setLoading, applySourceTypeUi, initCodeMirror, type SourceTypeState, type SourceTypeElements } from './feed-rules-core'

const DEFAULT_LIST_RULES = '{\n  "container": "",\n  "item": "",\n  "title": "",\n  "link": ""\n}'
const DEFAULT_CONTENT_RULES = '{\n  "title": "",\n  "body": "",\n  "date": "",\n  "image": "",\n  "author": "",\n  "is_vue_template": false,\n  "vue_json_field": ""\n}'

function renderPreviewTable(
  container: HTMLElement,
  items: PreviewItem[],
  mode: string
): void {
  if (items.length === 0) {
    container.innerHTML =
      '<div class="text-center text-muted py-4">No results found. Check your rules and try again.</div>'
    return
  }

  const showContent = mode !== 'list'
  const titleWidth = showContent ? '25%' : '40%'
  const urlWidth = showContent ? '15%' : '60%'

  let html = `<div class="table-responsive"><table class="table table-striped table-hover">
    <thead><tr>
      <th style="width:${titleWidth}">Title</th>
      <th style="width:${urlWidth}">${mode === 'list' ? 'URL' : 'Time'}</th>
      ${showContent ? '<th style="width:60%">Content Preview</th>' : ''}
    </tr></thead><tbody>`

  for (const item of items) {
    const titleCell = `<td>${escapeHtml(item.title || '')}</td>`

    let secondCell: string
    if (mode === 'list') {
      secondCell = item.url
        ? `<td><a href="${escapeAttr(item.url)}" target="_blank" rel="noreferrer" style="word-break:break-all">${escapeHtml(item.url)}</a></td>`
        : '<td></td>'
    } else {
      secondCell = `<td>${escapeHtml(item.published_at || 'N/A')}</td>`
    }

    let contentCell = ''
    if (showContent) {
      const content = item.content
        ? item.content.substring(0, 500) + (item.content.length > 500 ? '...' : '')
        : 'No content extracted'
      contentCell = `<td><div style="max-height:120px;overflow-y:auto;font-size:0.85rem">${escapeHtml(content)}</div></td>`
    }

    html += `<tr>${titleCell}${secondCell}${contentCell}</tr>`
  }

  html += '</tbody></table></div>'
  container.innerHTML = html
}

export function initFeedWizard(): void {
  const root = document.getElementById('feed-wizard')
  if (!root || root.dataset.inited) return
  root.dataset.inited = 'true'

  // RSS source type state
  let sourceType: 'html' | 'rss' = 'html'
  let rssFullContent = false
  let rssHasFullContent = false

  // Form elements
  const inputUrl = root.querySelector<HTMLInputElement>('#wizard-url')!
  const inputName = root.querySelector<HTMLInputElement>('#wizard-name')!
  const inputSampleUrl = root.querySelector<HTMLInputElement>('#input-sample-url')!
  const checkDebug = root.querySelector<HTMLInputElement>('#wizard-debug')!

  // Buttons
  const btnAnalyzeList = root.querySelector<HTMLButtonElement>('#btn-analyze-list')!
  const btnAnalyzeContent = root.querySelector<HTMLButtonElement>('#btn-analyze-content')!
  const btnTestList = root.querySelector<HTMLButtonElement>('#btn-test-list')!
  const btnTestContent = root.querySelector<HTMLButtonElement>('#btn-test-content')!
  const btnTestBoth = root.querySelector<HTMLButtonElement>('#btn-test-both')!
  const btnSave = root.querySelector<HTMLButtonElement>('#btn-save')!
  const btnToggleRules = root.querySelector<HTMLButtonElement>('#btn-toggle-rules')!

  // Panels
  const rulesPanel = root.querySelector<HTMLElement>('#rules-panel')!
  const previewSection = root.querySelector<HTMLElement>('#preview-section')!
  const previewBody = root.querySelector<HTMLElement>('#preview-body')!
  const previewError = root.querySelector<HTMLElement>('#preview-error')!
  const previewLoading = root.querySelector<HTMLElement>('#preview-loading')!
  const debugBanner = root.querySelector<HTMLElement>('#debug-banner')!
  const debugBannerPath = root.querySelector<HTMLElement>('#debug-banner-path')!

  // RSS toggle DOM refs
  const sourceTypeHtml = root.querySelector<HTMLButtonElement>('#source-type-html')!
  const sourceTypeRss = root.querySelector<HTMLButtonElement>('#source-type-rss')!
  const rssFullContentWrapper = root.querySelector<HTMLElement>('#rss-full-content-wrapper')!
  const rssFullContentCheck = root.querySelector<HTMLInputElement>('#rss-full-content-check')!
  const rssFullContentInfo = root.querySelector<HTMLElement>('#rss-full-content-info')!
  const listRulesSection = root.querySelector<HTMLElement>('#list-rules-section')!
  const contentRulesSection = root.querySelector<HTMLElement>('#content-rules-section')!

  // Initialize CodeMirror editors via shared module
  const cmListRules = initCodeMirror('cm-list-rules', DEFAULT_LIST_RULES)
  const cmContentRules = initCodeMirror('cm-content-rules', DEFAULT_CONTENT_RULES)

  // Helper: build state/elements objects and call shared applySourceTypeUi
  function callApplyUi(): void {
    const state: SourceTypeState = { sourceType, rssFullContent, rssHasFullContent }
    const els: SourceTypeElements = {
      sourceTypeHtml,
      sourceTypeRss,
      listRulesSection,
      contentRulesSection,
      analyzeListBtn: btnAnalyzeList,
      testListBtn: btnTestList,
      testBothBtn: btnTestBoth,
      rssFullContentWrapper
    }
    applySourceTypeUi(state, els)
  }

  // HTML/RSS toggle click handlers
  sourceTypeHtml?.addEventListener('click', () => {
    sourceType = 'html'
    rssFullContent = false
    rssHasFullContent = false
    if (rssFullContentCheck) rssFullContentCheck.checked = false
    callApplyUi()
  })

  sourceTypeRss?.addEventListener('click', () => {
    sourceType = 'rss'
    callApplyUi()
  })

  // Full content checkbox handler
  rssFullContentCheck?.addEventListener('change', () => {
    rssFullContent = rssFullContentCheck.checked
    callApplyUi()
  })

  // Rules panel toggle — simple d-none toggle, panel visible by default
  let rulesExpanded = true
  btnToggleRules.addEventListener('click', () => {
    rulesExpanded = !rulesExpanded
    if (rulesExpanded) {
      rulesPanel.classList.remove('d-none')
      btnToggleRules.innerHTML = '<i class="ri-code-line me-1"></i> Hide Rules JSON'
    } else {
      rulesPanel.classList.add('d-none')
      btnToggleRules.innerHTML = '<i class="ri-code-line me-1"></i> Show Rules JSON'
    }
  })

  // Analyze List
  btnAnalyzeList.addEventListener('click', async () => {
    const url = inputUrl.value.trim()
    if (!url) {
      alert('Please enter Target URL first')
      return
    }
    const restore = setLoading(
      btnAnalyzeList,
      '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Analyzing...'
    )
    // Disable the other analyze button to prevent concurrent analysis
    btnAnalyzeContent.disabled = true
    try {
      const data = await api.analyzeList(url, checkDebug.checked)
      const rulesStr = typeof data.rules === 'string'
        ? data.rules
        : JSON.stringify(data.rules, null, 2)
      if (cmListRules) cmListRules.setValue(rulesStr)
      // Auto-expand rules panel so user sees result
      if (!rulesExpanded) btnToggleRules.click()
      if (checkDebug.checked && data.debug_dir) {
        alert('Debug: ' + data.debug_dir)
      }
    } catch (err: unknown) {
      alert('Error analyzing list: ' + (err instanceof Error ? err.message : String(err)))
    } finally {
      restore()
      btnAnalyzeContent.disabled = false
    }
  })

  // Analyze Content
  btnAnalyzeContent.addEventListener('click', async () => {
    const sampleUrl = inputSampleUrl.value.trim()
    if (!sampleUrl) {
      alert('Please enter Sample Article URL first')
      return
    }
    const restore = setLoading(
      btnAnalyzeContent,
      '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Analyzing...'
    )
    // Disable the other analyze button to prevent concurrent analysis
    btnAnalyzeList.disabled = true
    try {
      const data = await api.analyzeContent(sampleUrl, checkDebug.checked)
      const rulesStr = typeof data.rules === 'string'
        ? data.rules
        : JSON.stringify(data.rules, null, 2)
      if (cmContentRules) cmContentRules.setValue(rulesStr)
      if (!rulesExpanded) btnToggleRules.click()
      if (checkDebug.checked && data.debug_dir) {
        alert('Debug: ' + data.debug_dir)
      }
    } catch (err: unknown) {
      alert('Error analyzing content: ' + (err instanceof Error ? err.message : String(err)))
    } finally {
      restore()
      btnAnalyzeList.disabled = false
    }
  })

  // Preview helper
  async function runPreview(mode: string, targetUrl?: string): Promise<void> {
    const url = inputUrl.value.trim()
    const resolvedUrl = targetUrl || url

    if (mode === 'list' && !url) {
      alert('Please enter a Target URL first.')
      return
    }
    if (mode === 'content' && !resolvedUrl) {
      alert('Please enter a Sample URL to test content extraction.')
      return
    }
    if (mode === 'both' && !url) {
      alert('Please enter a Target URL first.')
      return
    }

    // Show preview section, scroll to it
    previewSection.classList.remove('d-none')
    previewSection.scrollIntoView({ behavior: 'smooth', block: 'start' })

    // Reset state
    previewBody.innerHTML = ''
    previewError.classList.add('d-none')
    previewLoading.classList.remove('d-none')
    debugBanner.classList.add('d-none')

    // Update loading text
    const loadingLabel = mode === 'both' ? 'everything' : mode
    previewLoading.querySelector('.preview-loading-text')!.textContent =
      `Crawling and analyzing ${loadingLabel}...`

    try {
      const listRulesStr = cmListRules ? cmListRules.getValue() : DEFAULT_LIST_RULES
      const contentRulesStr = cmContentRules ? cmContentRules.getValue() : DEFAULT_CONTENT_RULES
      const payload: PreviewCrawlPayload = {
        url: resolvedUrl,
        list_rules: parseSafe(listRulesStr),
        content_rules: parseSafe(contentRulesStr),
        mode,
        target_url: targetUrl || undefined,
        source_type: sourceType
      }
      const res = await api.previewCrawl(payload, checkDebug.checked)

      if (res.status === 'success') {
        const firstItem = res.data?.[0] as PreviewItem & { error?: string }
        if (firstItem?.error) {
          previewError.textContent = String(firstItem.error)
          previewError.classList.remove('d-none')
        } else {
          renderPreviewTable(previewBody, res.data, mode)
          if (checkDebug.checked && res.debug_dir) {
            debugBannerPath.textContent = res.debug_dir
            debugBanner.classList.remove('d-none')
          }
        }
      }
    } catch (err: unknown) {
      previewError.textContent = err instanceof Error ? err.message : 'Preview failed'
      previewError.classList.remove('d-none')
    } finally {
      previewLoading.classList.add('d-none')
    }
  }

  // Test buttons
  btnTestList.addEventListener('click', async () => {
    if (sourceType === 'rss') {
      const url = inputUrl.value.trim()
      if (!url) { alert('Please enter a URL'); return }
      // Show preview section and loading state
      previewSection.classList.remove('d-none')
      previewSection.scrollIntoView({ behavior: 'smooth', block: 'start' })
      previewBody.innerHTML = ''
      previewError.classList.add('d-none')
      previewLoading.classList.remove('d-none')
      previewLoading.querySelector('.preview-loading-text')!.textContent = 'Parsing RSS feed...'
      debugBanner.classList.add('d-none')
      try {
        const result = await api.parseFeed(url)
        renderPreviewTable(previewBody, result.items.map(item => ({
          title: item.title,
          url: item.url,
          published_at: item.pub_date
        })), 'list')
        // Update full content detection
        rssHasFullContent = result.has_full_content
        if (rssHasFullContent && rssFullContentInfo) {
          rssFullContentInfo.textContent = `Feed contains full article content (${result.item_count} items)`
          rssFullContentInfo.style.display = ''
        }
        callApplyUi()
      } catch (e: unknown) {
        previewError.textContent = e instanceof Error ? e.message : 'Failed to parse RSS feed'
        previewError.classList.remove('d-none')
      } finally {
        previewLoading.classList.add('d-none')
      }
    } else {
      runPreview('list')
    }
  })
  btnTestContent.addEventListener('click', () =>
    runPreview('content', inputSampleUrl.value.trim() || undefined)
  )
  btnTestBoth.addEventListener('click', () => runPreview('both'))

  // Save
  btnSave.addEventListener('click', async () => {
    const url = inputUrl.value.trim()
    const name = inputName.value.trim()
    if (!url || !name) {
      alert('URL and Site Name are required')
      return
    }

    const listRulesStr = cmListRules ? cmListRules.getValue() : DEFAULT_LIST_RULES
    const contentRulesStr = cmContentRules ? cmContentRules.getValue() : DEFAULT_CONTENT_RULES

    let parsedList: Record<string, unknown>
    let parsedContent: Record<string, unknown>
    if (sourceType === 'rss') {
      parsedList = {}
    } else {
      try {
        parsedList = JSON.parse(listRulesStr)
      } catch {
        alert('Rules must be valid JSON. Please check your list rules.')
        return
      }
    }
    if (sourceType === 'rss' && rssFullContent) {
      parsedContent = {}
    } else {
      try {
        parsedContent = JSON.parse(contentRulesStr)
      } catch {
        alert('Rules must be valid JSON. Please check your content rules.')
        return
      }
    }

    const restore = setLoading(
      btnSave,
      '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Saving...'
    )
    try {
      await api.createSite({
        site: { url, name, refresh_frequency: 60, source_type: sourceType, rss_full_content: rssFullContent },
        rules: {
          list_rules: parsedList,
          content_rules: parsedContent
        }
      })
      alert('Feed created successfully!')
      const pagesPrefix = (import.meta as any).env?.DEV ? '' : '/pages'
      window.location.href = `${pagesPrefix}/dashboard`
    } catch (err: unknown) {
      alert('Error saving: ' + (err instanceof Error ? err.message : String(err)) + '\n(Make sure rules are valid JSON)')
    } finally {
      restore()
    }
  })
}
