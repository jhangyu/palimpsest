/* global HTMLElement, AbortController, KeyboardEvent, fetch */

export interface InboxMessage {
  id: string
  from: string
  fromEmail: string
  subject: string
  body: string
  date: string
  read: boolean
  starred: boolean
  folder: string
  avatar?: string
}

export interface InboxFolder {
  name: string
  icon: string
  count?: number
  key: string
}

const DEFAULT_FOLDERS: InboxFolder[] = [
  { name: 'Inbox', icon: 'ri-inbox-fill', count: 4, key: 'inbox' },
  { name: 'Sent', icon: 'ri-send-plane-fill', count: 0, key: 'sent' },
  { name: 'Drafts', icon: 'ri-draft-fill', count: 1, key: 'drafts' },
  { name: 'Starred', icon: 'ri-star-fill', count: 0, key: 'starred' },
  { name: 'Trash', icon: 'ri-delete-bin-fill', count: 0, key: 'trash' }
]

const SAMPLE_MESSAGES: InboxMessage[] = [
  {
    id: '1',
    from: 'Alice Chen',
    fromEmail: 'alice@example.com',
    subject: 'Q2 Revenue Report - Action Required',
    body: `<p>Hi,</p>
<p>Please review the attached Q2 revenue report at your earliest convenience. We need to finalize the numbers before the board meeting next Thursday.</p>
<p>Key highlights:</p>
<ul>
<li>Revenue up 15% QoQ</li>
<li>New customer acquisition rate improved by 22%</li>
<li>Churn rate decreased to 3.2%</li>
</ul>
<p>Let me know if you have any questions.</p>
<p>Best,<br>Alice</p>`,
    date: '2026-06-16',
    read: false,
    starred: true,
    folder: 'inbox'
  },
  {
    id: '2',
    from: 'Bob Martinez',
    fromEmail: 'bob@example.com',
    subject: 'Team offsite planning',
    body: `<p>Hey team,</p>
<p>I'm putting together the agenda for our team offsite next month. Please send me your topic suggestions by Friday.</p>
<p>Current agenda items:</p>
<ol>
<li>Product roadmap review</li>
<li>Engineering process improvements</li>
<li>Team building activities</li>
</ol>
<p>Looking forward to your input!</p>
<p>Cheers,<br>Bob</p>`,
    date: '2026-06-15',
    read: false,
    starred: false,
    folder: 'inbox'
  },
  {
    id: '3',
    from: 'Carol White',
    fromEmail: 'carol@example.com',
    subject: 'Design review feedback',
    body: `<p>Hi,</p>
<p>Great work on the new dashboard design. I have a few suggestions:</p>
<ul>
<li>Consider adding more whitespace between cards</li>
<li>The color contrast on secondary text could be improved</li>
<li>Mobile layout looks excellent</li>
</ul>
<p>Overall, I think we're in good shape for the launch.</p>
<p>Thanks,<br>Carol</p>`,
    date: '2026-06-14',
    read: true,
    starred: false,
    folder: 'inbox'
  },
  {
    id: '4',
    from: 'David Kim',
    fromEmail: 'david@example.com',
    subject: 'Infrastructure upgrade complete',
    body: `<p>Team,</p>
<p>The infrastructure upgrade has been completed successfully. Here's a summary:</p>
<ul>
<li>Database migrated to PostgreSQL 16</li>
<li>Cache layer upgraded to Redis 7</li>
<li>All services redeployed with zero downtime</li>
</ul>
<p>Monitoring shows improved response times across the board. Please report any issues.</p>
<p>Regards,<br>David</p>`,
    date: '2026-06-13',
    read: true,
    starred: false,
    folder: 'inbox'
  },
  {
    id: '5',
    from: 'Eva Johnson',
    fromEmail: 'eva@example.com',
    subject: 'Welcome to the team!',
    body: `<p>Hi everyone,</p>
<p>Please join me in welcoming our newest team member! They'll be joining the frontend team starting next Monday.</p>
<p>Let's make sure they have a smooth onboarding experience.</p>
<p>Best,<br>Eva</p>`,
    date: '2026-06-10',
    read: true,
    starred: true,
    folder: 'inbox'
  },
  {
    id: '6',
    from: 'Me',
    fromEmail: 'me@example.com',
    subject: 'Re: Project timeline',
    body: `<p>Hi Frank,</p>
<p>Thanks for the update. The revised timeline works for our team. We'll adjust our sprint planning accordingly.</p>
<p>Best,<br>Me</p>`,
    date: '2026-06-12',
    read: true,
    starred: false,
    folder: 'sent'
  },
  {
    id: '7',
    from: 'Me',
    fromEmail: 'me@example.com',
    subject: 'Draft: Marketing campaign proposal',
    body: `<p>Draft notes for the marketing campaign...</p>
<p>TODO: Add budget breakdown and timeline.</p>`,
    date: '2026-06-11',
    read: true,
    starred: false,
    folder: 'drafts'
  }
]

interface InboxState {
  folders: InboxFolder[]
  messages: InboxMessage[]
  currentFolder: string
  selectedMessageId: string | null
  selectedIndex: number
}

function getInitials(name: string): string {
  return name.split(' ').map((w) => w[0]).join('').toUpperCase().slice(0, 2)
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days}d ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function renderFolderList(state: InboxState): string {
  return state.folders.map((f) => {
    const isActive = state.currentFolder === f.key
    const count = f.key === 'starred'
      ? state.messages.filter((m) => m.starred).length
      : (f.count || 0)
    return `<a href="#" class="list-group-item list-group-item-action d-flex align-items-center${isActive ? ' active' : ''}" data-folder="${f.key}">
      <i class="${f.icon} me-2"></i>
      <span class="flex-grow-1">${f.name}</span>
      ${count > 0 ? `<span class="badge ${isActive ? 'bg-light text-dark' : 'bg-primary'} rounded-pill">${count}</span>` : ''}
    </a>`
  }).join('')
}

function renderMessageList(state: InboxState): string {
  const filtered = state.currentFolder === 'starred'
    ? state.messages.filter((m) => m.starred)
    : state.messages.filter((m) => m.folder === state.currentFolder)

  if (filtered.length === 0) {
    return '<div class="text-muted text-center p-4">No messages</div>'
  }

  return filtered.map((msg, idx) => {
    const isSelected = msg.id === state.selectedMessageId
    const unread = !msg.read ? 'fw-bold' : ''
    return `<div class="inbox-msg-item p-3 border-bottom${isSelected ? ' bg-light' : ''}${unread ? ' ' + unread : ''}" data-msg-id="${msg.id}" data-msg-index="${idx}" role="button">
      <div class="d-flex align-items-start">
        <div class="avatar-circle me-2 flex-shrink-0">${getInitials(msg.from)}</div>
        <div class="flex-grow-1 overflow-hidden">
          <div class="d-flex justify-content-between align-items-center mb-1">
            <span class="text-truncate ${unread}">${msg.from}</span>
            <small class="text-muted ms-2 flex-shrink-0">${formatDate(msg.date)}</small>
          </div>
          <div class="text-truncate small ${unread}">${msg.subject}</div>
        </div>
        <button class="btn btn-sm border-0 ms-1 star-btn flex-shrink-0" data-star-id="${msg.id}" title="Toggle star">
          <i class="${msg.starred ? 'ri-star-fill text-warning' : 'ri-star-line text-muted'}"></i>
        </button>
      </div>
    </div>`
  }).join('')
}

function renderPreview(state: InboxState): string {
  if (!state.selectedMessageId) {
    return `<div class="d-flex flex-column align-items-center justify-content-center h-100 text-muted p-4">
      <i class="ri-mail-open-line" style="font-size:3rem"></i>
      <p class="mt-2">Select a message to read</p>
      <small>Use <kbd>J</kbd>/<kbd>K</kbd> to navigate, <kbd>S</kbd> to star, <kbd>R</kbd> to reply</small>
    </div>`
  }

  const msg = state.messages.find((m) => m.id === state.selectedMessageId)
  if (!msg) return ''

  return `<div class="p-4">
    <div class="d-flex justify-content-between align-items-start mb-3">
      <div>
        <h5 class="mb-1">${msg.subject}</h5>
        <div class="text-muted small">
          <strong>${msg.from}</strong> &lt;${msg.fromEmail}&gt;
          <span class="ms-2">${msg.date}</span>
        </div>
      </div>
      <div class="d-flex gap-1">
        <button class="btn btn-sm btn-outline-secondary" data-action="reply" title="Reply (R)">
          <i class="ri-reply-line"></i>
        </button>
        <button class="btn btn-sm btn-outline-secondary" data-action="delete" title="Delete">
          <i class="ri-delete-bin-line"></i>
        </button>
        <button class="btn btn-sm btn-outline-secondary star-btn" data-star-id="${msg.id}" title="Star (S)">
          <i class="${msg.starred ? 'ri-star-fill text-warning' : 'ri-star-line'}"></i>
        </button>
      </div>
    </div>
    <hr>
    <div class="message-body">${msg.body}</div>
  </div>`
}

export function initInbox() {
  document.querySelectorAll<HTMLElement>('.inbox-app:not([data-inited])').forEach((container) => {
    container.dataset.inited = 'true'

    let folderData: InboxFolder[]
    try {
      folderData = JSON.parse(container.dataset.folders || '[]')
      if (!folderData.length) folderData = DEFAULT_FOLDERS
    } catch {
      folderData = DEFAULT_FOLDERS
    }

    const state: InboxState = {
      folders: folderData,
      messages: [...SAMPLE_MESSAGES],
      currentFolder: 'inbox',
      selectedMessageId: null,
      selectedIndex: -1
    }

    const folderEl = container.querySelector<HTMLElement>('.inbox-folders')
    const listEl = container.querySelector<HTMLElement>('.inbox-list')
    const previewEl = container.querySelector<HTMLElement>('.inbox-preview')

    if (!folderEl || !listEl || !previewEl) return

    const abortController = new AbortController()

    function getFilteredMessages(): InboxMessage[] {
      return state.currentFolder === 'starred'
        ? state.messages.filter((m) => m.starred)
        : state.messages.filter((m) => m.folder === state.currentFolder)
    }

    function render() {
      folderEl!.innerHTML = renderFolderList(state)
      listEl!.innerHTML = renderMessageList(state)
      previewEl!.innerHTML = renderPreview(state)
      bindEvents()
    }

    function selectMessage(id: string | null) {
      state.selectedMessageId = id
      if (id) {
        const msg = state.messages.find((m) => m.id === id)
        if (msg) msg.read = true
        const filtered = getFilteredMessages()
        state.selectedIndex = filtered.findIndex((m) => m.id === id)
      }
      render()
    }

    function toggleStar(id: string) {
      const msg = state.messages.find((m) => m.id === id)
      if (msg) {
        msg.starred = !msg.starred
        // Update starred folder count
        const starredFolder = state.folders.find((f) => f.key === 'starred')
        if (starredFolder) {
          starredFolder.count = state.messages.filter((m) => m.starred).length
        }
        render()
      }
    }

    function bindEvents() {
      // Folder click
      folderEl!.querySelectorAll<HTMLElement>('[data-folder]').forEach((el) => {
        el.addEventListener('click', (e) => {
          e.preventDefault()
          state.currentFolder = el.dataset.folder || 'inbox'
          state.selectedMessageId = null
          state.selectedIndex = -1
          render()
        })
      })

      // Message click
      listEl!.querySelectorAll<HTMLElement>('.inbox-msg-item').forEach((el) => {
        el.addEventListener('click', (e) => {
          // Don't select when clicking star
          if ((e.target as HTMLElement).closest('.star-btn')) return
          selectMessage(el.dataset.msgId || null)
        })
      })

      // Star buttons (both in list and preview)
      container.querySelectorAll<HTMLElement>('.star-btn[data-star-id]').forEach((el) => {
        el.addEventListener('click', (e) => {
          e.stopPropagation()
          toggleStar(el.dataset.starId || '')
        })
      })

      // Reply button
      container.querySelectorAll<HTMLElement>('[data-action="reply"]').forEach((el) => {
        el.addEventListener('click', () => {
          const msg = state.messages.find((m) => m.id === state.selectedMessageId)
          if (msg) {
            alert(`Reply to: ${msg.from} <${msg.fromEmail}>`)
          }
        })
      })

      // Delete button
      container.querySelectorAll<HTMLElement>('[data-action="delete"]').forEach((el) => {
        el.addEventListener('click', () => {
          if (state.selectedMessageId) {
            const msg = state.messages.find((m) => m.id === state.selectedMessageId)
            if (msg) {
              msg.folder = 'trash'
              state.selectedMessageId = null
              state.selectedIndex = -1
              // Update counts
              const inboxFolder = state.folders.find((f) => f.key === 'inbox')
              if (inboxFolder) {
                inboxFolder.count = state.messages.filter((m) => m.folder === 'inbox' && !m.read).length
              }
              const trashFolder = state.folders.find((f) => f.key === 'trash')
              if (trashFolder) {
                trashFolder.count = state.messages.filter((m) => m.folder === 'trash').length
              }
              render()
            }
          }
        })
      })
    }

    // Keyboard shortcuts
    function handleKeydown(e: KeyboardEvent) {
      // Don't capture if user is typing in an input
      if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'TEXTAREA') return

      const filtered = getFilteredMessages()

      switch (e.key.toLowerCase()) {
        case 'j': {
          // Next message
          e.preventDefault()
          const nextIdx = Math.min(state.selectedIndex + 1, filtered.length - 1)
          if (filtered[nextIdx]) selectMessage(filtered[nextIdx].id)
          break
        }
        case 'k': {
          // Previous message
          e.preventDefault()
          const prevIdx = Math.max(state.selectedIndex - 1, 0)
          if (filtered[prevIdx]) selectMessage(filtered[prevIdx].id)
          break
        }
        case 's': {
          // Star/unstar
          e.preventDefault()
          if (state.selectedMessageId) toggleStar(state.selectedMessageId)
          break
        }
        case 'r': {
          // Reply
          e.preventDefault()
          const msg = state.messages.find((m) => m.id === state.selectedMessageId)
          if (msg) {
            alert(`Reply to: ${msg.from} <${msg.fromEmail}>`)
          }
          break
        }
      }
    }

    document.addEventListener('keydown', handleKeydown, { signal: abortController.signal })

    // Cleanup on page swap
    document.addEventListener('astro:before-swap', () => {
      abortController.abort()
    }, { once: true })

    // Try fetching from API, fallback to sample data
    fetch('/api/messages')
      .then((res) => {
        if (!res.ok) throw new Error('API unavailable')
        return res.json()
      })
      .then((data: InboxMessage[]) => {
        if (Array.isArray(data) && data.length > 0) {
          state.messages = data
          render()
        }
      })
      .catch(() => {
        // Use sample data (already set)
      })

    render()
  })
}
