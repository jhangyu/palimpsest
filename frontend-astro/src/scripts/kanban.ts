/* global document, localStorage, HTMLElement, DragEvent, Event */

interface KanbanCard {
  id: string
  title: string
  description?: string
  color?: string
}

interface KanbanColumn {
  id: string
  title: string
  cards: KanbanCard[]
}

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7)
}

function loadState(key: string, fallback: KanbanColumn[]): KanbanColumn[] {
  try {
    const raw = localStorage.getItem(key)
    if (raw) return JSON.parse(raw) as KanbanColumn[]
  } catch { /* empty */ }
  return fallback
}

function saveState(key: string, columns: KanbanColumn[]) {
  localStorage.setItem(key, JSON.stringify(columns))
}

function renderBoard(container: HTMLElement, columns: KanbanColumn[]) {
  container.innerHTML = columns.map(col => `
    <div class="col kanban-column" data-column-id="${col.id}">
      <div class="card h-100">
        <div class="card-header d-flex justify-content-between align-items-center bg-body-tertiary">
          <h6 class="mb-0">${col.title}</h6>
          <span class="badge bg-secondary">${col.cards.length}</span>
        </div>
        <div class="card-body kanban-drop-zone p-2" data-column-id="${col.id}" style="min-height:120px">
          ${col.cards.map(card => `
            <div class="card mb-2 kanban-card shadow-sm" draggable="true" data-card-id="${card.id}" data-column-id="${col.id}" style="${card.color ? 'border-left:4px solid ' + card.color : 'border-left:4px solid var(--bs-primary)'}">
              <div class="card-body p-2">
                <div class="d-flex justify-content-between align-items-start">
                  <strong class="small">${card.title}</strong>
                  <div class="btn-group btn-group-sm">
                    <button class="btn btn-link btn-sm p-0 text-muted kanban-edit-btn" data-card-id="${card.id}" data-column-id="${col.id}" title="Edit">
                      <i class="ri-pencil-line"></i>
                    </button>
                    <button class="btn btn-link btn-sm p-0 text-danger kanban-delete-btn ms-2" data-card-id="${card.id}" data-column-id="${col.id}" title="Delete">
                      <i class="ri-delete-bin-line"></i>
                    </button>
                  </div>
                </div>
                ${card.description ? `<p class="text-muted small mb-0 mt-1">${card.description}</p>` : ''}
              </div>
            </div>
          `).join('')}
        </div>
        <div class="card-footer bg-body-tertiary">
          <button class="btn btn-sm btn-outline-primary w-100 kanban-add-btn" data-column-id="${col.id}">
            <i class="ri-add-line me-1"></i>Add Card
          </button>
        </div>
      </div>
    </div>
  `).join('')
}

export function initKanban() {
  const board = document.getElementById('kanban-board')
  if (!board || board.dataset.inited) return
  board.dataset.inited = 'true'

  const storageKey = board.dataset.storageKey || 'kanban-state'
  let defaultColumns: KanbanColumn[] = []
  try {
    defaultColumns = JSON.parse(board.dataset.defaultColumns || '[]')
  } catch { /* empty */ }

  let columns = loadState(storageKey, defaultColumns)
  let draggedCardId: string | null = null
  let draggedFromColumn: string | null = null

  const modal = document.getElementById('kanban-modal')
  const modalTitle = modal?.querySelector<HTMLElement>('.modal-title')
  const modalForm = modal?.querySelector<HTMLFormElement>('#kanban-card-form')
  const titleInput = modal?.querySelector<HTMLInputElement>('#kanban-card-title')
  const descInput = modal?.querySelector<HTMLTextAreaElement>('#kanban-card-desc')
  const colorInput = modal?.querySelector<HTMLInputElement>('#kanban-card-color')
  const hiddenCardId = modal?.querySelector<HTMLInputElement>('#kanban-card-id')
  const hiddenColId = modal?.querySelector<HTMLInputElement>('#kanban-col-id')

  let bsModal: { show: () => void, hide: () => void } | null = null
  if (modal && typeof window !== 'undefined' && (window as unknown as Record<string, unknown>).bootstrap) {
    // eslint-disable-next-line no-unused-vars
    const Bootstrap = (window as unknown as Record<string, unknown>).bootstrap as Record<string, new (el: HTMLElement) => { show: () => void, hide: () => void }>
    bsModal = new Bootstrap.Modal(modal)
  }

  function refresh() {
    renderBoard(board!, columns)
    saveState(storageKey, columns)
    attachDragListeners()
    attachButtonListeners()
  }

  function attachDragListeners() {
    board!.querySelectorAll<HTMLElement>('.kanban-card').forEach(card => {
      card.addEventListener('dragstart', (e: DragEvent) => {
        draggedCardId = card.dataset.cardId || null
        draggedFromColumn = card.dataset.columnId || null
        card.classList.add('opacity-50')
        if (e.dataTransfer) {
          e.dataTransfer.effectAllowed = 'move'
          e.dataTransfer.setData('text/plain', draggedCardId || '')
        }
      })
      card.addEventListener('dragend', () => {
        card.classList.remove('opacity-50')
        board!.querySelectorAll('.kanban-drop-zone').forEach(z => z.classList.remove('bg-primary-subtle'))
        draggedCardId = null
        draggedFromColumn = null
      })
    })

    board!.querySelectorAll<HTMLElement>('.kanban-drop-zone').forEach(zone => {
      zone.addEventListener('dragover', (e: DragEvent) => {
        e.preventDefault()
        if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
        zone.classList.add('bg-primary-subtle')
      })
      zone.addEventListener('dragleave', () => {
        zone.classList.remove('bg-primary-subtle')
      })
      zone.addEventListener('drop', (e: DragEvent) => {
        e.preventDefault()
        zone.classList.remove('bg-primary-subtle')
        const targetColId = zone.dataset.columnId
        if (!draggedCardId || !draggedFromColumn || !targetColId) return

        const srcCol = columns.find(c => c.id === draggedFromColumn)
        const dstCol = columns.find(c => c.id === targetColId)
        if (!srcCol || !dstCol) return

        const cardIdx = srcCol.cards.findIndex(c => c.id === draggedCardId)
        if (cardIdx === -1) return

        const [card] = srcCol.cards.splice(cardIdx, 1)
        dstCol.cards.push(card)
        refresh()
      })
    })
  }

  function attachButtonListeners() {
    board!.querySelectorAll<HTMLElement>('.kanban-add-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const colId = btn.dataset.columnId
        if (!colId || !modalTitle || !titleInput || !descInput || !colorInput || !hiddenCardId || !hiddenColId) return
        modalTitle.textContent = 'Add Card'
        titleInput.value = ''
        descInput.value = ''
        colorInput.value = '#0d6efd'
        hiddenCardId.value = ''
        hiddenColId.value = colId
        if (bsModal) bsModal.show()
      })
    })

    board!.querySelectorAll<HTMLElement>('.kanban-edit-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const cardId = btn.dataset.cardId
        const colId = btn.dataset.columnId
        if (!cardId || !colId || !modalTitle || !titleInput || !descInput || !colorInput || !hiddenCardId || !hiddenColId) return
        const col = columns.find(c => c.id === colId)
        const card = col?.cards.find(c => c.id === cardId)
        if (!card) return
        modalTitle.textContent = 'Edit Card'
        titleInput.value = card.title
        descInput.value = card.description || ''
        colorInput.value = card.color || '#0d6efd'
        hiddenCardId.value = cardId
        hiddenColId.value = colId
        if (bsModal) bsModal.show()
      })
    })

    board!.querySelectorAll<HTMLElement>('.kanban-delete-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const cardId = btn.dataset.cardId
        const colId = btn.dataset.columnId
        if (!cardId || !colId) return
        const col = columns.find(c => c.id === colId)
        if (!col) return
        col.cards = col.cards.filter(c => c.id !== cardId)
        refresh()
      })
    })
  }

  if (modalForm) {
    modalForm.addEventListener('submit', (e: Event) => {
      e.preventDefault()
      const colId = hiddenColId?.value
      const cardId = hiddenCardId?.value
      const title = titleInput?.value.trim()
      const description = descInput?.value.trim()
      const color = colorInput?.value

      if (!title || !colId) return

      const col = columns.find(c => c.id === colId)
      if (!col) return

      if (cardId) {
        const card = col.cards.find(c => c.id === cardId)
        if (card) {
          card.title = title
          card.description = description || undefined
          card.color = color || undefined
        }
      } else {
        col.cards.push({
          id: generateId(),
          title,
          description: description || undefined,
          color: color || undefined
        })
      }

      if (bsModal) bsModal.hide()
      refresh()
    })
  }

  refresh()

  ;(board as unknown as Record<string, unknown>).__kanbanCleanup = () => {
    board!.removeAttribute('data-inited')
  }
}

export function destroyKanban() {
  const board = document.getElementById('kanban-board')
  if (!board) return
  const cleanup = (board as unknown as Record<string, unknown>).__kanbanCleanup as (() => void) | undefined
  if (cleanup) cleanup()
}
