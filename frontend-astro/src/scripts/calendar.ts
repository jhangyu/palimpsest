/* global document, localStorage, HTMLElement, Event */

interface CalendarEvent {
  id: string
  title: string
  date: string
  color?: string
}

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7)
}

function loadEvents(key: string, fallback: CalendarEvent[]): CalendarEvent[] {
  try {
    const raw = localStorage.getItem(key)
    if (raw) return JSON.parse(raw) as CalendarEvent[]
  } catch { /* empty */ }
  return fallback
}

function saveEvents(key: string, events: CalendarEvent[]) {
  localStorage.setItem(key, JSON.stringify(events))
}

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate()
}

function getFirstDayOfWeek(year: number, month: number): number {
  return new Date(year, month, 1).getDay()
}

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
]

const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function formatDate(year: number, month: number, day: number): string {
  const m = String(month + 1).padStart(2, '0')
  const d = String(day).padStart(2, '0')
  return `${year}-${m}-${d}`
}

function renderCalendar(
  container: HTMLElement,
  year: number,
  month: number,
  events: CalendarEvent[]
) {
  const daysInMonth = getDaysInMonth(year, month)
  const firstDay = getFirstDayOfWeek(year, month)
  const today = new Date()
  const isCurrentMonth = today.getFullYear() === year && today.getMonth() === month
  const todayDate = today.getDate()

  let html = `
    <div class="d-flex justify-content-between align-items-center mb-3">
      <button class="btn btn-sm btn-outline-secondary cal-prev-btn">
        <i class="ri-arrow-left-s-line"></i>
      </button>
      <h5 class="mb-0">${MONTH_NAMES[month]} ${year}</h5>
      <button class="btn btn-sm btn-outline-secondary cal-next-btn">
        <i class="ri-arrow-right-s-line"></i>
      </button>
    </div>
    <div class="table-responsive">
      <table class="table table-bordered mb-0 calendar-grid">
        <thead>
          <tr>
            ${DAY_NAMES.map(d => `<th class="text-center bg-body-tertiary small py-2">${d}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
  `

  let dayCounter = 1
  const totalCells = Math.ceil((firstDay + daysInMonth) / 7) * 7

  for (let i = 0; i < totalCells; i++) {
    if (i % 7 === 0) html += '<tr>'

    if (i < firstDay || dayCounter > daysInMonth) {
      html += '<td class="bg-body-tertiary" style="min-height:80px">&nbsp;</td>'
    } else {
      const dateStr = formatDate(year, month, dayCounter)
      const dayEvents = events.filter(e => e.date === dateStr)
      const isToday = isCurrentMonth && dayCounter === todayDate

      html += `
        <td class="cal-day position-relative ${isToday ? 'table-primary' : ''}" data-date="${dateStr}" style="min-height:80px;cursor:pointer;vertical-align:top;width:14.28%">
          <div class="d-flex justify-content-between align-items-start">
            <span class="small fw-medium ${isToday ? 'badge bg-primary rounded-pill' : ''}">${dayCounter}</span>
          </div>
          <div class="mt-1">
            ${dayEvents.map(ev => `
              <div class="cal-event badge w-100 text-start text-truncate mb-1" data-event-id="${ev.id}" style="background-color:${ev.color || 'var(--bs-primary)'};cursor:pointer;font-size:.7rem">
                ${ev.title}
              </div>
            `).join('')}
          </div>
        </td>
      `
      dayCounter++
    }

    if (i % 7 === 6) html += '</tr>'
  }

  html += '</tbody></table></div>'
  container.innerHTML = html
}

export function initCalendar() {
  const wrapper = document.getElementById('calendar-app')
  if (!wrapper || wrapper.dataset.inited) return
  wrapper.dataset.inited = 'true'

  const storageKey = wrapper.dataset.storageKey || 'calendar-events'
  let defaultEvents: CalendarEvent[] = []
  try {
    defaultEvents = JSON.parse(wrapper.dataset.defaultEvents || '[]')
  } catch { /* empty */ }

  let events = loadEvents(storageKey, defaultEvents)
  const now = new Date()
  let currentYear = now.getFullYear()
  let currentMonth = now.getMonth()

  const grid = wrapper.querySelector<HTMLElement>('.calendar-grid-container')
  const modal = document.getElementById('calendar-modal')
  const modalTitle = modal?.querySelector<HTMLElement>('.modal-title')
  const modalForm = modal?.querySelector<HTMLFormElement>('#calendar-event-form')
  const eventTitleInput = modal?.querySelector<HTMLInputElement>('#calendar-event-title')
  const eventDateInput = modal?.querySelector<HTMLInputElement>('#calendar-event-date')
  const eventColorInput = modal?.querySelector<HTMLInputElement>('#calendar-event-color')
  const hiddenEventId = modal?.querySelector<HTMLInputElement>('#calendar-event-id')
  const deleteBtn = modal?.querySelector<HTMLElement>('#calendar-event-delete')

  let bsModal: { show: () => void, hide: () => void } | null = null
  if (modal && typeof window !== 'undefined' && (window as unknown as Record<string, unknown>).bootstrap) {
    // eslint-disable-next-line no-unused-vars
    const Bootstrap = (window as unknown as Record<string, unknown>).bootstrap as Record<string, new (el: HTMLElement) => { show: () => void, hide: () => void }>
    bsModal = new Bootstrap.Modal(modal)
  }

  function refresh() {
    if (!grid) return
    renderCalendar(grid, currentYear, currentMonth, events)
    saveEvents(storageKey, events)
    attachListeners()
  }

  function attachListeners() {
    if (!grid) return

    grid.querySelector('.cal-prev-btn')?.addEventListener('click', () => {
      currentMonth--
      if (currentMonth < 0) {
        currentMonth = 11
        currentYear--
      }
      refresh()
    })

    grid.querySelector('.cal-next-btn')?.addEventListener('click', () => {
      currentMonth++
      if (currentMonth > 11) {
        currentMonth = 0
        currentYear++
      }
      refresh()
    })

    grid.querySelectorAll<HTMLElement>('.cal-day').forEach(cell => {
      cell.addEventListener('click', (e) => {
        const target = e.target as HTMLElement
        const eventEl = target.closest('.cal-event')
        if (eventEl) {
          const eventId = (eventEl as HTMLElement).dataset.eventId
          const ev = events.find(x => x.id === eventId)
          if (!ev) return
          openModal('Edit Event', ev.title, ev.date, ev.color || '#0d6efd', ev.id)
        } else {
          const date = cell.dataset.date || ''
          openModal('Add Event', '', date, '#0d6efd', '')
        }
      })
    })
  }

  function openModal(title: string, evTitle: string, date: string, color: string, id: string) {
    if (!modalTitle || !eventTitleInput || !eventDateInput || !eventColorInput || !hiddenEventId || !deleteBtn) return
    modalTitle.textContent = title
    eventTitleInput.value = evTitle
    eventDateInput.value = date
    eventColorInput.value = color
    hiddenEventId.value = id
    deleteBtn.style.display = id ? 'inline-block' : 'none'
    if (bsModal) bsModal.show()
  }

  if (modalForm) {
    modalForm.addEventListener('submit', (e: Event) => {
      e.preventDefault()
      const title = eventTitleInput?.value.trim()
      const date = eventDateInput?.value
      const color = eventColorInput?.value
      const id = hiddenEventId?.value

      if (!title || !date) return

      if (id) {
        const ev = events.find(x => x.id === id)
        if (ev) {
          ev.title = title
          ev.date = date
          ev.color = color || undefined
        }
      } else {
        events.push({
          id: generateId(),
          title,
          date,
          color: color || undefined
        })
      }

      if (bsModal) bsModal.hide()
      refresh()
    })
  }

  if (deleteBtn) {
    deleteBtn.addEventListener('click', () => {
      const id = hiddenEventId?.value
      if (!id) return
      events = events.filter(x => x.id !== id)
      if (bsModal) bsModal.hide()
      refresh()
    })
  }

  refresh()

  ;(wrapper as unknown as Record<string, unknown>).__calendarCleanup = () => {
    wrapper!.removeAttribute('data-inited')
  }
}

export function destroyCalendar() {
  const wrapper = document.getElementById('calendar-app')
  if (!wrapper) return
  const cleanup = (wrapper as unknown as Record<string, unknown>).__calendarCleanup as (() => void) | undefined
  if (cleanup) cleanup()
}
