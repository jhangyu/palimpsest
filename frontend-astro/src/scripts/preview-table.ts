import type { PreviewItem } from './api'
import { escapeHtml } from '@/scripts/utils'

/**
 * Render preview results into the container as a Bootstrap table.
 * @param container     Target DOM element
 * @param results       Array of preview items from the crawl API
 * @param mode          'list' | 'content' | 'both'
 * @param filteredUrls  Optional set of URLs that were filtered out
 * @param filterSummary Optional summary from backend filter engine
 */
export function renderPreview(
  container: HTMLElement,
  results: PreviewItem[],
  mode: string,
  filteredUrls?: Set<string>,
  filterSummary?: { passed: number; filtered_out: number }
): void {
  container.innerHTML = ''

  if (results.length === 0) {
    container.innerHTML = `
      <div class="text-center text-muted py-5">
        <i class="ri-error-warning-line fs-3 d-block mb-2"></i>
        No results found. Please check your rules.
      </div>`
    return
  }

  // Filter summary banner
  const filteredCount =
    filterSummary?.filtered_out ?? filteredUrls?.size ?? 0
  if (filteredCount > 0) {
    const banner = document.createElement('div')
    banner.className =
      'alert alert-warning d-flex align-items-center gap-2 py-2 px-3 mb-3'
    banner.innerHTML = `
      <i class="ri-filter-line"></i>
      <span><strong>${filteredCount}</strong> article${filteredCount !== 1 ? 's' : ''} hidden by filter rules</span>`
    container.appendChild(banner)
  }

  const isListMode = mode === 'list'

  const table = document.createElement('table')
  table.className = 'table table-striped table-hover mb-0'

  // thead
  const thead = document.createElement('thead')
  let headHtml = '<tr>'
  headHtml += `<th style="width:${isListMode ? '40%' : '25%'}">Title</th>`
  headHtml += `<th style="width:${isListMode ? '60%' : '15%'}">${isListMode ? 'URL' : 'Time'}</th>`
  if (!isListMode) {
    headHtml += '<th style="width:60%">Content Preview</th>'
  }
  headHtml += '</tr>'
  thead.innerHTML = headHtml
  table.appendChild(thead)

  // tbody
  const tbody = document.createElement('tbody')
  for (const item of results) {
    const tr = document.createElement('tr')

    const isFiltered = filteredUrls
      ? filteredUrls.has(item.url ?? '')
      : Boolean(item.filtered)

    if (isFiltered) {
      tr.classList.add('opacity-50')
      tr.style.textDecoration = 'line-through'
    }

    // Title cell
    const tdTitle = document.createElement('td')
    if (isFiltered) {
      const badge = document.createElement('span')
      badge.className = 'badge bg-secondary me-1'
      badge.textContent = 'Filtered'
      tdTitle.appendChild(badge)
    }
    const titleText = document.createTextNode(item.title || '')
    tdTitle.appendChild(titleText)
    tr.appendChild(tdTitle)

    // URL or Time cell
    const tdSecond = document.createElement('td')
    if (isListMode) {
      if (item.url) {
        const a = document.createElement('a')
        a.href = item.url
        a.target = '_blank'
        a.rel = 'noreferrer'
        a.style.wordBreak = 'break-all'
        a.textContent = item.url
        tdSecond.appendChild(a)
      } else {
        tdSecond.textContent = 'N/A'
      }
    } else {
      const span = document.createElement('span')
      span.className = 'text-muted small'
      span.textContent = item.published_at || 'N/A'
      tdSecond.appendChild(span)
    }
    tr.appendChild(tdSecond)

    // Content cell (non-list modes)
    if (!isListMode) {
      const tdContent = document.createElement('td')
      const wrapper = document.createElement('div')
      wrapper.style.maxHeight = '120px'
      wrapper.style.overflowY = 'auto'
      wrapper.style.fontSize = '13px'
      if (item.content) {
        const truncated =
          item.content.length > 500
            ? item.content.substring(0, 500) + '...'
            : item.content
        wrapper.textContent = truncated
      } else {
        wrapper.classList.add('text-muted')
        wrapper.textContent = 'No content extracted'
      }
      tdContent.appendChild(wrapper)
      tr.appendChild(tdContent)
    }

    tbody.appendChild(tr)
  }
  table.appendChild(tbody)

  const wrapper = document.createElement('div')
  wrapper.className = 'table-responsive'
  wrapper.appendChild(table)
  container.appendChild(wrapper)
}

/**
 * Show a loading spinner with a message inside the container.
 * @param container  Target DOM element
 * @param mode       The test mode label to display
 */
export function showLoading(container: HTMLElement, mode: string): void {
  const label =
    mode === 'both'
      ? 'everything'
      : mode === 'list'
        ? 'list'
        : 'content'
  container.innerHTML = `
    <div class="d-flex flex-column align-items-center justify-content-center py-5 text-muted">
      <span class="spinner-border spinner-border-sm mb-3" style="width:2rem;height:2rem;" role="status"></span>
      <p class="mb-0 fw-medium">Crawling and analyzing ${label}...</p>
    </div>`
}

/**
 * Display an error message inside the container.
 * @param container  Target DOM element
 * @param message    Error message string
 */
export function showError(container: HTMLElement, message: string): void {
  container.innerHTML = `
    <div class="alert alert-danger d-flex align-items-center gap-2 mb-0" role="alert">
      <i class="ri-error-warning-line"></i>
      <span>${escapeHtml(message)}</span>
    </div>`
}

/**
 * Clear all content from the container.
 * @param container  Target DOM element
 */
export function clearPreview(container: HTMLElement): void {
  container.innerHTML = ''
}

/**
 * Show the debug artifacts banner.
 * @param container  Target DOM element (prepend)
 * @param debugDir   Path to debug directory
 */
export function showDebugBanner(
  container: HTMLElement,
  debugDir: string
): void {
  const existing = container.querySelector('.debug-dir-banner')
  if (existing) existing.remove()

  const banner = document.createElement('div')
  banner.className =
    'debug-dir-banner alert alert-info d-flex align-items-center gap-2 py-2 px-3 mb-3'
  banner.innerHTML = `
    <i class="ri-bug-line"></i>
    <span>Debug artifacts saved to:</span>
    <code class="flex-grow-1 text-break">${escapeHtml(debugDir)}</code>
    <button class="btn btn-sm btn-outline-info" type="button" title="Copy path">
      <i class="ri-clipboard-line"></i>
    </button>`
  const copyBtn = banner.querySelector('button')!
  copyBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(debugDir).then(() => {
      copyBtn.innerHTML = '<i class="ri-check-line"></i>'
      setTimeout(() => {
        copyBtn.innerHTML = '<i class="ri-clipboard-line"></i>'
      }, 2000)
    })
  })
  container.prepend(banner)
}
