/**
 * Articles page runtime: fetches /articles/list and renders a
 * TanStack Table with filter tabs, search, pagination, and CSV export.
 */
import {
  createTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel
} from '@tanstack/table-core'
import type { ColumnDef, ColumnFiltersState, PaginationState, SortingState, Updater } from '@tanstack/table-core'
import { api } from './api'
import type { ArticleListItem } from './api'

// --- Badge color helpers ---

const BADGE_COLORS = ['bg-primary', 'bg-success', 'bg-info', 'bg-warning', 'bg-danger', 'bg-secondary']

function feedBadgeColor(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = ((hash << 5) - hash + name.charCodeAt(i)) | 0
  return BADGE_COLORS[Math.abs(hash) % BADGE_COLORS.length]
}

// --- Formatting helpers ---

function fmtTime(iso: string): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-TW', {
      timeZone: 'Asia/Taipei',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return iso.slice(0, 16)
  }
}

// --- Security helpers (same pattern as analytics.ts) ---

function escapeHtml(s: string): string {
  const el = document.createElement('span')
  el.textContent = s
  return el.innerHTML
}

function escapeAttr(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function safeUrl(url: string): string {
  return /^https?:\/\//i.test(url) ? url : '#'
}

// --- DOM helpers ---

function showEl(id: string, show: boolean) {
  const el = document.getElementById(id)
  if (el) el.style.display = show ? '' : 'none'
}

// --- Custom cell rendering ---

function renderCell(colId: string, item: ArticleListItem): string {
  switch (colId) {
    case 'article_title': {
      const title = escapeHtml(item.article_title)
      const oriUrl = escapeAttr(safeUrl(item.ori_url))
      if (item.image_url) {
        const imgSrc = escapeAttr(item.image_url)
        return `<div class="d-flex align-items-center gap-2">` +
          `<div style="position:relative;width:40px;height:40px;min-width:40px;flex-shrink:0">` +
          `<img src="${imgSrc}" alt="" loading="lazy" class="rounded" style="width:40px;height:40px;object-fit:cover;display:block" ` +
          `onerror="this.style.display='none';this.nextElementSibling.style.display='flex'" />` +
          `<div class="align-items-center justify-content-center rounded bg-light" style="width:40px;height:40px;position:absolute;top:0;left:0;display:none">` +
          `<i class="ri-image-line text-muted"></i></div>` +
          `</div>` +
          `<a href="${oriUrl}" target="_blank" rel="noopener">${title}</a></div>`
      }
      return `<div class="d-flex align-items-center gap-2">` +
        `<div class="d-flex align-items-center justify-content-center rounded bg-light" style="width:40px;height:40px;min-width:40px;">` +
        `<i class="ri-image-line text-muted"></i></div>` +
        `<a href="${oriUrl}" target="_blank" rel="noopener">${title}</a></div>`
    }
    case 'feed_name': {
      const name = escapeHtml(item.feed_name)
      const color = feedBadgeColor(item.feed_name)
      return `<span class="badge ${color}">${name}</span>`
    }
    case 'word_count':
      return `<span class="text-end d-block">${item.word_count.toLocaleString('en-US')}</span>`
    case 'update_time':
      return fmtTime(item.update_time)
    default:
      return escapeHtml(String((item as unknown as Record<string, unknown>)[colId] ?? ''))
  }
}

// --- Build page number array (same as table.ts) ---

function buildPageNumbers(current: number, total: number): number[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i)
  }
  const pages: number[] = []
  pages.push(0)
  if (current > 2) pages.push(-1)
  const start = Math.max(1, current - 1)
  const end = Math.min(total - 2, current + 1)
  for (let i = start; i <= end; i++) pages.push(i)
  if (current < total - 3) pages.push(-1)
  pages.push(total - 1)
  return pages
}

// --- Main articles table init ---

let currentFilter = 'all'
let currentTable: ReturnType<typeof createTable<ArticleListItem>> | null = null
let toolbarBound = false

export async function initArticles() {
  // Reset toolbar binding so listeners are re-attached after page navigation
  toolbarBound = false
  showEl('articlesLoadingState', true)
  showEl('articlesErrorState', false)
  showEl('articlesContent', false)

  try {
    const data = await api.getArticlesList(currentFilter, '', 1, 100)
    showEl('articlesLoadingState', false)
    showEl('articlesContent', true)

    updateFilterCounts(data.filter_counts)
    buildArticlesTable(data.articles)
    bindFilterTabs()
  } catch (err) {
    showEl('articlesLoadingState', false)
    const errEl = document.getElementById('articlesErrorState')
    if (errEl) {
      errEl.style.display = ''
      errEl.textContent = `Failed to load articles: ${err instanceof Error ? err.message : String(err)}`
    }
    console.error('[Articles] Load error:', err)
  }
}

function updateFilterCounts(counts: { today: number; week: number; month: number; all: number }) {
  const tabs = document.querySelectorAll<HTMLAnchorElement>('#articlesFilterTabs [data-filter]')
  tabs.forEach(tab => {
    const filter = tab.dataset.filter as keyof typeof counts
    const badge = tab.querySelector('.badge')
    if (badge && filter in counts) {
      badge.textContent = String(counts[filter])
    }
  })
}

function bindFilterTabs() {
  const tabs = document.querySelectorAll<HTMLAnchorElement>('#articlesFilterTabs [data-filter]')
  tabs.forEach(tab => {
    tab.addEventListener('click', async (e) => {
      e.preventDefault()
      const filter = tab.dataset.filter as string
      if (filter === currentFilter) return

      // Update active tab
      tabs.forEach(t => {
        t.classList.remove('active', 'border-bottom', 'border-2', 'border-dark')
      })
      tab.classList.add('active', 'border-bottom', 'border-2', 'border-dark')
      currentFilter = filter

      // Reload data
      showEl('articlesLoadingState', true)
      showEl('articlesContent', false)
      showEl('articlesErrorState', false)

      try {
        const data = await api.getArticlesList(currentFilter, '', 1, 100)
        showEl('articlesLoadingState', false)
        showEl('articlesContent', true)
        updateFilterCounts(data.filter_counts)

        // Rebuild table with new data
        const container = document.getElementById('articlesTableContainer')
        if (container) container.innerHTML = ''
        buildArticlesTable(data.articles)
      } catch (err) {
        showEl('articlesLoadingState', false)
        const errEl = document.getElementById('articlesErrorState')
        if (errEl) {
          errEl.style.display = ''
          errEl.textContent = `Failed to load articles: ${err instanceof Error ? err.message : String(err)}`
        }
        console.error('[Articles] Filter error:', err)
      }
    })
  })
}

function buildArticlesTable(articles: ArticleListItem[]) {
  const container = document.getElementById('articlesTableContainer')
  if (!container) return

  const columns: ColumnDef<ArticleListItem>[] = [
    { id: 'article_title', accessorKey: 'article_title', header: 'Title', enableSorting: true },
    { id: 'feed_name', accessorKey: 'feed_name', header: 'Feed', enableSorting: true },
    {
      id: 'word_count',
      accessorKey: 'word_count',
      header: 'Words',
      enableSorting: true,
      filterFn: (row, columnId, filterValue: [number | null, number | null]) => {
        const val = row.getValue<number>(columnId)
        const [min, max] = filterValue
        if (min != null && val < min) return false
        if (max != null && val > max) return false
        return true
      }
    },
    { id: 'update_time', accessorKey: 'update_time', header: 'Updated', enableSorting: true }
  ]

  const tableEl = document.createElement('table')
  tableEl.className = 'table table-striped table-hover'
  container.appendChild(tableEl)

  let sorting: SortingState = []
  let globalFilter = ''
  let columnFilters: ColumnFiltersState = []
  let pagination: PaginationState = { pageIndex: 0, pageSize: 50 }

  const options = {
    data: articles,
    columns,
    renderFallbackValue: null,
    onStateChange: () => {},
    state: {
      sorting,
      globalFilter,
      columnFilters,
      columnPinning: { left: [], right: [] },
      columnVisibility: {},
      rowSelection: {},
      expanded: {},
      pagination
    },
    onSortingChange: (updater: Updater<SortingState>) => {
      sorting = typeof updater === 'function' ? updater(sorting) : updater
      table.options.state = { ...table.options.state, sorting }
      renderTable()
    },
    onGlobalFilterChange: (updater: Updater<string>) => {
      globalFilter = typeof updater === 'function' ? updater(globalFilter) : updater
      table.options.state = { ...table.options.state, globalFilter }
      renderTable()
    },
    onColumnFiltersChange: (updater: Updater<ColumnFiltersState>) => {
      columnFilters = typeof updater === 'function' ? updater(columnFilters) : updater
      table.options.state = { ...table.options.state, columnFilters }
      renderTable()
    },
    onPaginationChange: (updater: Updater<PaginationState>) => {
      pagination = typeof updater === 'function' ? updater(pagination) : updater
      table.options.state = { ...table.options.state, pagination }
      renderTable()
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel()
  }

  const table = createTable(options)

  // Expose this table instance and bind toolbar controls
  currentTable = table
  populateFeedFilter(articles)
  bindToolbar()

  // --- Pagination container ---
  const paginationDiv = document.createElement('div')
  paginationDiv.className = 'd-flex align-items-center justify-content-between mt-3 flex-wrap gap-2'
  container.appendChild(paginationDiv)

  // --- Render functions ---

  function renderTable() {
    tableEl.innerHTML = ''

    // thead
    const thead = document.createElement('thead')
    for (const headerGroup of table.getHeaderGroups()) {
      const tr = document.createElement('tr')
      for (const header of headerGroup.headers) {
        const th = document.createElement('th')
        th.scope = 'col'
        th.style.cursor = header.column.getCanSort() ? 'pointer' : 'default'
        th.style.userSelect = 'none'

        const label =
          typeof header.column.columnDef.header === 'string'
            ? header.column.columnDef.header
            : header.column.id
        const sortDir = header.column.getIsSorted()
        const indicator = sortDir === 'asc' ? ' ▲' : sortDir === 'desc' ? ' ▼' : ''
        th.textContent = label + indicator

        if (header.column.getCanSort()) {
          th.addEventListener('click', () => header.column.toggleSorting())
        }
        tr.appendChild(th)
      }
      thead.appendChild(tr)
    }
    tableEl.appendChild(thead)

    // tbody
    const tbody = document.createElement('tbody')
    const rows = table.getRowModel().rows

    if (rows.length === 0) {
      const tr = document.createElement('tr')
      const td = document.createElement('td')
      td.colSpan = columns.length
      td.className = 'text-center text-muted py-4'
      td.textContent = 'No articles found'
      tr.appendChild(td)
      tbody.appendChild(tr)
    } else {
      for (const row of rows) {
        const tr = document.createElement('tr')
        for (const cell of row.getVisibleCells()) {
          const td = document.createElement('td')
          td.innerHTML = renderCell(cell.column.id, row.original)
          tr.appendChild(td)
        }
        tbody.appendChild(tr)
      }
    }
    tableEl.appendChild(tbody)

    renderPagination()
  }

  function renderPagination() {
    paginationDiv.innerHTML = ''

    const pageCount = table.getPageCount()
    const pageIndex = table.getState().pagination.pageIndex
    const pageSize = table.getState().pagination.pageSize
    const totalRows = table.getFilteredRowModel().rows.length
    const start = pageIndex * pageSize + 1
    const end = Math.min((pageIndex + 1) * pageSize, totalRows)

    // Info
    const info = document.createElement('div')
    info.className = 'text-secondary small'
    info.setAttribute('aria-live', 'polite')
    info.textContent =
      totalRows > 0 ? `Showing ${start}–${end} of ${totalRows}` : 'No records'
    paginationDiv.appendChild(info)

    // Controls wrapper
    const controlsWrap = document.createElement('div')
    controlsWrap.className = 'd-flex align-items-center gap-3'

    // Rows per page
    const rppWrap = document.createElement('div')
    rppWrap.className = 'd-flex align-items-center gap-2'
    const rppLabel = document.createElement('label')
    rppLabel.className = 'text-secondary small'
    rppLabel.textContent = 'Rows:'
    const rppSelect = document.createElement('select')
    rppSelect.className = 'form-select form-select-sm'
    rppSelect.style.width = 'auto'
    rppSelect.style.minWidth = '70px'
    rppSelect.setAttribute('aria-label', 'Rows per page')
    for (const size of [10, 25, 50, 100]) {
      const opt = document.createElement('option')
      opt.value = String(size)
      opt.textContent = String(size)
      if (size === pageSize) opt.selected = true
      rppSelect.appendChild(opt)
    }
    rppSelect.addEventListener('change', () => {
      table.setPageSize(Number(rppSelect.value))
    })
    rppWrap.appendChild(rppLabel)
    rppWrap.appendChild(rppSelect)
    controlsWrap.appendChild(rppWrap)

    // Page buttons
    const nav = document.createElement('nav')
    nav.setAttribute('aria-label', 'Articles pagination')
    const ul = document.createElement('ul')
    ul.className = 'pagination pagination-sm mb-0'

    // Previous
    const prevLi = document.createElement('li')
    prevLi.className = 'page-item' + (pageIndex === 0 ? ' disabled' : '')
    const prevBtn = document.createElement('button')
    prevBtn.className = 'page-link'
    prevBtn.textContent = 'Previous'
    prevBtn.setAttribute('aria-label', 'Previous page')
    if (pageIndex > 0) {
      prevBtn.addEventListener('click', () => table.previousPage())
    }
    prevLi.appendChild(prevBtn)
    ul.appendChild(prevLi)

    // Page numbers
    const pages = buildPageNumbers(pageIndex, pageCount)
    for (const p of pages) {
      const li = document.createElement('li')
      if (p === -1) {
        li.className = 'page-item disabled'
        const span = document.createElement('span')
        span.className = 'page-link'
        span.textContent = '...'
        li.appendChild(span)
      } else {
        li.className = 'page-item' + (p === pageIndex ? ' active' : '')
        const btn = document.createElement('button')
        btn.className = 'page-link'
        btn.textContent = String(p + 1)
        btn.setAttribute('aria-label', `Page ${p + 1}`)
        if (p !== pageIndex) {
          btn.addEventListener('click', () => table.setPageIndex(p))
        }
        li.appendChild(btn)
      }
      ul.appendChild(li)
    }

    // Next
    const nextLi = document.createElement('li')
    nextLi.className = 'page-item' + (pageIndex >= pageCount - 1 ? ' disabled' : '')
    const nextBtn = document.createElement('button')
    nextBtn.className = 'page-link'
    nextBtn.textContent = 'Next'
    nextBtn.setAttribute('aria-label', 'Next page')
    if (pageIndex < pageCount - 1) {
      nextBtn.addEventListener('click', () => table.nextPage())
    }
    nextLi.appendChild(nextBtn)
    ul.appendChild(nextLi)

    nav.appendChild(ul)
    controlsWrap.appendChild(nav)
    paginationDiv.appendChild(controlsWrap)
  }

  // Initial render
  renderTable()
}

// --- CSV export ---

function exportCSV(
  table: ReturnType<typeof createTable<ArticleListItem>>
) {
  const headerLabels = ['Title', 'Feed', 'Words', 'Updated', 'URL']

  const rows = table.getFilteredRowModel().rows.map(row => {
    const item = row.original
    return [
      item.article_title,
      item.feed_name,
      String(item.word_count),
      fmtTime(item.update_time),
      item.ori_url
    ].map(val => {
      const str = val ?? ''
      return str.includes(',') || str.includes('"') || str.includes('\n')
        ? `"${str.replace(/"/g, '""')}"`
        : str
    }).join(',')
  })

  const csv = [headerLabels.join(','), ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'articles.csv'
  a.click()
  URL.revokeObjectURL(url)
}

// --- Feed filter population ---

function populateFeedFilter(articles: ArticleListItem[]) {
  const select = document.getElementById('filterFeedSource') as HTMLSelectElement | null
  if (!select) return

  const feeds = Array.from(new Set(articles.map(a => a.feed_name))).sort()
  select.innerHTML = '<option value="">All Feeds</option>'
  for (const feed of feeds) {
    const opt = document.createElement('option')
    opt.value = feed
    opt.textContent = feed
    select.appendChild(opt)
  }
}

// --- Toolbar binding (runs once per page load; uses currentTable ref) ---

function bindToolbar() {
  if (toolbarBound) return
  toolbarBound = true

  // Search
  const searchInput = document.getElementById('articlesSearchInput') as HTMLInputElement | null
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      currentTable?.setGlobalFilter(searchInput.value)
    })
  }

  // Export CSV
  const exportBtn = document.getElementById('articlesExportBtn')
  if (exportBtn) {
    exportBtn.addEventListener('click', () => {
      if (currentTable) exportCSV(currentTable)
    })
  }

  // Apply Filters
  const applyBtn = document.getElementById('articlesApplyFilter')
  if (applyBtn) {
    applyBtn.addEventListener('click', () => {
      if (!currentTable) return

      const feedSelect = document.getElementById('filterFeedSource') as HTMLSelectElement | null
      const minInput = document.getElementById('filterWordCountMin') as HTMLInputElement | null
      const maxInput = document.getElementById('filterWordCountMax') as HTMLInputElement | null

      const filters: ColumnFiltersState = []

      if (feedSelect?.value) {
        filters.push({ id: 'feed_name', value: feedSelect.value })
      }

      const min = minInput?.value !== '' ? Number(minInput?.value) : null
      const max = maxInput?.value !== '' ? Number(maxInput?.value) : null
      if (min !== null || max !== null) {
        filters.push({ id: 'word_count', value: [min, max] as [number | null, number | null] })
      }

      currentTable.setColumnFilters(filters)

      // Close offcanvas
      const drawerEl = document.getElementById('articlesFilterDrawer')
      if (drawerEl) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const bsOffcanvas = (window as any).bootstrap?.Offcanvas?.getInstance(drawerEl)
        bsOffcanvas?.hide()
      }
    })
  }

  // Reset Filters
  const resetBtn = document.getElementById('articlesResetFilter')
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      if (!currentTable) return

      currentTable.setColumnFilters([])

      const feedSelect = document.getElementById('filterFeedSource') as HTMLSelectElement | null
      const minInput = document.getElementById('filterWordCountMin') as HTMLInputElement | null
      const maxInput = document.getElementById('filterWordCountMax') as HTMLInputElement | null
      if (feedSelect) feedSelect.value = ''
      if (minInput) minInput.value = ''
      if (maxInput) maxInput.value = ''
    })
  }
}
