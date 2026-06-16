import {
  createTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel
} from '@tanstack/table-core'
import type {
  ColumnDef,
  Table,
  SortingState,
  RowSelectionState,
  Updater
} from '@tanstack/table-core'

type Row = Record<string, unknown>

export function initTables() {
  document
    .querySelectorAll<HTMLElement>('[data-table]:not([data-inited])')
    .forEach((container) => {
      container.dataset.inited = 'true'

      const columns: ColumnDef<Row>[] = JSON.parse(
        container.dataset.tableColumns || '[]'
      )
      const data: Row[] = JSON.parse(container.dataset.tableData || '[]')
      const selectable = container.hasAttribute('data-selectable')
      const exportFilename = container.dataset.export

      // Build wrapper elements
      const tableEl = document.createElement('table')
      tableEl.className = 'table table-striped table-hover'
      container.appendChild(tableEl)

      let sorting: SortingState = []
      let globalFilter = ''
      let rowSelection: RowSelectionState = {}

      const options = {
        data,
        columns,
        renderFallbackValue: null,
        onStateChange: () => {},
        state: {
          sorting,
          globalFilter,
          ...(selectable ? { rowSelection } : {})
        },
        onSortingChange: (updater: Updater<SortingState>) => {
          sorting =
            typeof updater === 'function' ? updater(sorting) : updater
          table.options.state = { ...table.options.state, sorting }
          renderTable()
        },
        onGlobalFilterChange: (updater: Updater<string>) => {
          globalFilter =
            typeof updater === 'function' ? updater(globalFilter) : updater
          table.options.state = { ...table.options.state, globalFilter }
          renderTable()
        },
        ...(selectable
          ? {
              enableRowSelection: true,
              onRowSelectionChange: (updater: Updater<RowSelectionState>) => {
                rowSelection =
                  typeof updater === 'function'
                    ? updater(rowSelection)
                    : updater
                table.options.state = {
                  ...table.options.state,
                  rowSelection
                }
                renderTable()
              }
            }
          : {}),
        getCoreRowModel: getCoreRowModel(),
        getSortedRowModel: getSortedRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
        getPaginationRowModel: getPaginationRowModel()
      }

      const table = createTable(options)

      // Search input
      const searchDiv = document.createElement('div')
      searchDiv.className = 'd-flex align-items-center gap-2 mb-3'
      const searchInput = document.createElement('input')
      searchInput.type = 'text'
      searchInput.className = 'form-control'
      searchInput.placeholder = 'Search...'
      searchInput.setAttribute('aria-label', 'Search table')
      searchInput.addEventListener('input', () => {
        table.setGlobalFilter(searchInput.value)
      })
      searchDiv.appendChild(searchInput)

      // Export button
      if (exportFilename) {
        const exportBtn = document.createElement('button')
        exportBtn.className = 'btn btn-sm btn-outline-secondary'
        exportBtn.textContent = 'Export CSV'
        exportBtn.addEventListener('click', () =>
          exportCSV(table, exportFilename)
        )
        searchDiv.appendChild(exportBtn)
      }

      container.insertBefore(searchDiv, tableEl)

      // Pagination container
      const paginationDiv = document.createElement('div')
      paginationDiv.className =
        'd-flex align-items-center justify-content-between mt-3 flex-wrap gap-2'
      container.appendChild(paginationDiv)

      function renderTable() {
        tableEl.innerHTML = ''

        // thead
        const thead = document.createElement('thead')
        for (const headerGroup of table.getHeaderGroups()) {
          const tr = document.createElement('tr')

          if (selectable) {
            const th = document.createElement('th')
            th.scope = 'col'
            th.style.width = '40px'
            const cb = document.createElement('input')
            cb.type = 'checkbox'
            cb.className = 'form-check-input'
            cb.setAttribute('aria-label', 'Select all rows')
            cb.checked = table.getIsAllPageRowsSelected()
            cb.indeterminate = table.getIsSomePageRowsSelected()
            cb.addEventListener('change', () => {
              table.toggleAllPageRowsSelected(cb.checked)
            })
            th.appendChild(cb)
            tr.appendChild(th)
          }

          for (const header of headerGroup.headers) {
            const th = document.createElement('th')
            th.scope = 'col'
            th.style.cursor = header.column.getCanSort()
              ? 'pointer'
              : 'default'
            th.style.userSelect = 'none'

            const label =
              typeof header.column.columnDef.header === 'string'
                ? header.column.columnDef.header
                : header.column.id
            const sortDir = header.column.getIsSorted()
            const indicator = sortDir === 'asc'
              ? ' ▲'
              : sortDir === 'desc'
                ? ' ▼'
                : ''
            th.textContent = label + indicator

            if (header.column.getCanSort()) {
              th.addEventListener('click', () => {
                header.column.toggleSorting()
              })
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
          const colCount =
            table.getAllColumns().length + (selectable ? 1 : 0)
          td.colSpan = colCount
          td.className = 'text-center text-muted py-4'
          td.textContent = 'No data found'
          tr.appendChild(td)
          tbody.appendChild(tr)
        } else {
          for (const row of rows) {
            const tr = document.createElement('tr')

            if (selectable) {
              const td = document.createElement('td')
              const cb = document.createElement('input')
              cb.type = 'checkbox'
              cb.className = 'form-check-input'
              cb.setAttribute('aria-label', 'Select row')
              cb.checked = row.getIsSelected()
              cb.addEventListener('change', () => {
                row.toggleSelected(cb.checked)
              })
              td.appendChild(cb)
              tr.appendChild(td)
            }

            for (const cell of row.getVisibleCells()) {
              const td = document.createElement('td')
              const value = cell.getValue()
              td.textContent = value != null ? String(value) : ''
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
          totalRows > 0
            ? `Showing ${start}-${end} of ${totalRows}`
            : 'No records'
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
        rppSelect.setAttribute('aria-label', 'Rows per page')
        for (const size of [5, 10, 25, 50]) {
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
        nav.setAttribute('aria-label', 'Table pagination')
        const ul = document.createElement('ul')
        ul.className = 'pagination pagination-sm mb-0'

        // Previous
        const prevLi = document.createElement('li')
        prevLi.className =
          'page-item' + (pageIndex === 0 ? ' disabled' : '')
        const prevBtn = document.createElement('button')
        prevBtn.className = 'page-link'
        prevBtn.textContent = 'Previous'
        prevBtn.setAttribute('aria-label', 'Previous page')
        if (pageIndex > 0) {
          prevBtn.addEventListener('click', () => table.previousPage())
        }
        prevLi.appendChild(prevBtn)
        ul.appendChild(prevLi)

        // Page numbers (show max 7 buttons with ellipsis)
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
            li.className =
              'page-item' + (p === pageIndex ? ' active' : '')
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
        nextLi.className =
          'page-item' +
          (pageIndex >= pageCount - 1 ? ' disabled' : '')
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
    })
}

function buildPageNumbers(
  current: number,
  total: number
): number[] {
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

function exportCSV<T>(table: Table<T>, filename: string) {
  const headers = table.getAllColumns().map((c) => c.id)
  const rows = table.getFilteredRowModel().rows.map((row) =>
    headers
      .map((h) => {
        const val = row.getValue(h)
        const str = val != null ? String(val) : ''
        return str.includes(',') || str.includes('"')
          ? `"${str.replace(/"/g, '""')}"`
          : str
      })
      .join(',')
  )
  const csv = [headers.join(','), ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${filename}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
