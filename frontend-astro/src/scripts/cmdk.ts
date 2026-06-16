/* global document, window, HTMLElement, requestAnimationFrame */

interface CmdkItem {
  title: string
  description: string
  icon: string
  href: string
}

const NAV_ITEMS: CmdkItem[] = [
  { title: 'Dashboard', description: 'Overview of business metrics', icon: 'ri-dashboard-line', href: '/dashboard' },
  { title: 'Analytics', description: 'Charts and data analysis', icon: 'ri-line-chart-line', href: '/analytics' },
  { title: 'Kanban Board', description: 'Task management board', icon: 'ri-layout-column-line', href: '/apps/kanban' },
  { title: 'Calendar', description: 'Event calendar', icon: 'ri-calendar-line', href: '/apps/calendar' },
  { title: 'Settings', description: 'Application settings', icon: 'ri-settings-3-line', href: '/settings' },
  { title: 'Form Controls', description: 'Input elements and forms', icon: 'ri-file-list-3-line', href: '/forms/form-controls' },
  { title: 'Select', description: 'Select dropdowns', icon: 'ri-file-list-3-line', href: '/forms/select' },
  { title: 'Radio & Checkbox', description: 'Radio and checkbox inputs', icon: 'ri-file-list-3-line', href: '/forms/radio-checkbox' },
  { title: 'Switches', description: 'Toggle switches', icon: 'ri-file-list-3-line', href: '/forms/switches' },
  { title: 'Basic Tables', description: 'Simple table layouts', icon: 'ri-table-line', href: '/tables/basic' },
  { title: 'Enhanced Tables', description: 'Tables with extra features', icon: 'ri-table-line', href: '/tables/enhanced' },
  { title: 'Advanced Tables', description: 'Complex table configurations', icon: 'ri-table-line', href: '/tables/advanced' },
  { title: 'Datatable', description: 'Interactive data tables', icon: 'ri-table-line', href: '/tables/datatable' },
  { title: 'Add User', description: 'Create a new user', icon: 'ri-user-line', href: '/users/add' },
  { title: 'List Users', description: 'View all users', icon: 'ri-user-line', href: '/users/list' },
  { title: 'Profile', description: 'User profile page', icon: 'ri-user-line', href: '/users/profile' },
  { title: 'Accordion', description: 'Collapsible content panels', icon: 'ri-layout-grid-line', href: '/interface/accordion' },
  { title: 'Alerts', description: 'Contextual alert messages', icon: 'ri-layout-grid-line', href: '/interface/alerts' },
  { title: 'Badges', description: 'Labels and badges', icon: 'ri-layout-grid-line', href: '/interface/badges' },
  { title: 'Buttons', description: 'Button styles and variants', icon: 'ri-layout-grid-line', href: '/interface/buttons' },
  { title: 'Cards', description: 'Card components', icon: 'ri-layout-grid-line', href: '/interface/cards' },
  { title: 'Modal', description: 'Dialog and modal windows', icon: 'ri-layout-grid-line', href: '/interface/modal' },
  { title: 'Toasts', description: 'Toast notifications', icon: 'ri-layout-grid-line', href: '/interface/toasts' },
  { title: 'Typography', description: 'Text styles and fonts', icon: 'ri-layout-grid-line', href: '/interface/typography' }
]

function fuzzyScore(query: string, text: string): number {
  const q = query.toLowerCase()
  const t = text.toLowerCase()
  if (t.includes(q)) {
    return t.indexOf(q) === 0 ? 100 : 50
  }
  let qi = 0
  let score = 0
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      score += 10
      qi++
    }
  }
  return qi === q.length ? score : 0
}

function filterItems(query: string): CmdkItem[] {
  if (!query.trim()) return NAV_ITEMS
  const scored = NAV_ITEMS
    .map(item => ({
      item,
      score: Math.max(
        fuzzyScore(query, item.title),
        fuzzyScore(query, item.description) * 0.7
      )
    }))
    .filter(s => s.score > 0)
    .sort((a, b) => b.score - a.score)
  return scored.map(s => s.item)
}

let debounceTimer: ReturnType<typeof setTimeout> | null = null

function debounce(fn: () => void, ms: number) {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(fn, ms)
}

function renderResults(container: HTMLElement, items: CmdkItem[], activeIndex: number) {
  container.innerHTML = items.length
    ? items.map((item, i) => `
      <a href="${item.href}" class="list-group-item list-group-item-action d-flex align-items-center gap-3 ${i === activeIndex ? 'active' : ''}" data-cmdk-index="${i}">
        <i class="${item.icon} fs-5 flex-shrink-0"></i>
        <div>
          <div class="fw-medium">${item.title}</div>
          <small class="opacity-75">${item.description}</small>
        </div>
      </a>
    `).join('')
    : '<div class="text-center text-muted py-4">No results found</div>'
}

export function initCommandPalette() {
  const wrapper = document.getElementById('cmdk-palette')
  if (!wrapper || wrapper.dataset.inited) return
  wrapper.dataset.inited = 'true'

  const backdrop = wrapper.querySelector<HTMLElement>('.cmdk-backdrop')
  const dialog = wrapper.querySelector<HTMLElement>('.cmdk-dialog')
  const input = wrapper.querySelector<HTMLInputElement>('.cmdk-input')
  const results = wrapper.querySelector<HTMLElement>('.cmdk-results')
  if (!backdrop || !dialog || !input || !results) return

  let isOpen = false
  let activeIndex = 0
  let currentItems: CmdkItem[] = [...NAV_ITEMS]

  function open() {
    isOpen = true
    wrapper!.classList.add('cmdk-open')
    wrapper!.style.display = 'block'
    input!.value = ''
    activeIndex = 0
    currentItems = [...NAV_ITEMS]
    renderResults(results!, currentItems, activeIndex)
    requestAnimationFrame(() => input!.focus())
  }

  function close() {
    isOpen = false
    wrapper!.classList.remove('cmdk-open')
    wrapper!.style.display = 'none'
  }

  function navigate(index: number) {
    if (currentItems.length === 0) return
    activeIndex = ((index % currentItems.length) + currentItems.length) % currentItems.length
    renderResults(results!, currentItems, activeIndex)
    const activeEl = results!.querySelector('.active')
    if (activeEl) activeEl.scrollIntoView({ block: 'nearest' })
  }

  function selectCurrent() {
    if (currentItems[activeIndex]) {
      window.location.href = currentItems[activeIndex].href
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault()
      if (isOpen) close()
      else open()
      return
    }
    if (!isOpen) return
    switch (e.key) {
    case 'Escape':
      e.preventDefault()
      close()
      break
    case 'ArrowDown':
      e.preventDefault()
      navigate(activeIndex + 1)
      break
    case 'ArrowUp':
      e.preventDefault()
      navigate(activeIndex - 1)
      break
    case 'Enter':
      e.preventDefault()
      selectCurrent()
      break
    }
  }

  function handleInput() {
    debounce(() => {
      const query = input!.value
      currentItems = filterItems(query)
      activeIndex = 0
      renderResults(results!, currentItems, activeIndex)
    }, 150)
  }

  document.addEventListener('keydown', handleKeydown)
  backdrop!.addEventListener('click', close)
  input!.addEventListener('input', handleInput)

  results!.addEventListener('click', (e) => {
    const target = (e.target as HTMLElement).closest('[data-cmdk-index]')
    if (target) {
      const idx = parseInt(target.getAttribute('data-cmdk-index')!, 10)
      if (currentItems[idx]) {
        window.location.href = currentItems[idx].href
      }
    }
  })

  // Store cleanup references
  ;(wrapper as unknown as Record<string, unknown>).__cmdkCleanup = () => {
    document.removeEventListener('keydown', handleKeydown)
    backdrop!.removeEventListener('click', close)
    input!.removeEventListener('input', handleInput)
    if (debounceTimer) clearTimeout(debounceTimer)
    wrapper!.removeAttribute('data-inited')
  }
}

export function destroyCommandPalette() {
  const wrapper = document.getElementById('cmdk-palette')
  if (!wrapper) return
  const cleanup = (wrapper as unknown as Record<string, unknown>).__cmdkCleanup as (() => void) | undefined
  if (cleanup) cleanup()
}
