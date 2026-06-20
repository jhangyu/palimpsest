/* global fetch */

interface Notification {
  feed_source: string
  fail_type: string
  count: number
  time: string
  site_id: number
}

interface NotificationPrefs {
  fail_crawl?: boolean
  ai_reanalyze?: boolean
  fail_access?: boolean
}

const FAIL_TYPE_ICONS: Record<string, string> = {
  'Fail Crawl': 'ri-error-warning-line',
  'AI Re-analyze': 'ri-brain-line',
  'Fail Access': 'ri-wifi-off-line'
}

const FAIL_TYPE_KEYS: Record<string, string> = {
  'Fail Crawl': 'fail_crawl',
  'AI Re-analyze': 'ai_reanalyze',
  'Fail Access': 'fail_access'
}

function relativeTime(isoString: string): string {
  const now = Date.now()
  const then = new Date(isoString).getTime()
  const diffSec = Math.floor((now - then) / 1000)
  if (diffSec < 60) return 'just now'
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay}d ago`
}

let pollTimer: ReturnType<typeof setInterval> | null = null

async function fetchNotifications(): Promise<Notification[]> {
  try {
    const res = await fetch('/api/notifications?limit=10', { credentials: 'same-origin' })
    if (!res.ok) return []
    return await res.json()
  } catch {
    return []
  }
}

async function fetchPrefs(): Promise<NotificationPrefs> {
  try {
    const res = await fetch('/api/users/me', { credentials: 'same-origin' })
    if (!res.ok) return {}
    const data = await res.json()
    return data.preferences?.notifications || {}
  } catch {
    return {}
  }
}

function renderNotifications(notifications: Notification[]): void {
  const listEl = document.querySelector('.notifications-list')
  if (!listEl) return

  if (notifications.length === 0) {
    listEl.innerHTML = `
      <div class="text-center text-muted py-3">
        <i class="ri-notification-off-line fs-4"></i>
        <p class="small mb-0 mt-1">No new notifications</p>
      </div>`
    updateBadge(0)
    return
  }

  listEl.innerHTML = notifications.map(n => {
    const icon = FAIL_TYPE_ICONS[n.fail_type] || 'ri-notification-3-line'
    return `
      <div class="d-flex align-items-start gap-3 px-3 py-2 border-bottom">
        <i class="${icon} fs-5 text-warning mt-1"></i>
        <div class="flex-grow-1 min-w-0">
          <div class="fw-medium text-truncate">${escapeHtml(n.feed_source)}</div>
          <div class="small text-muted">${escapeHtml(n.fail_type)} &middot; ${n.count} occurrence${n.count > 1 ? 's' : ''}</div>
        </div>
        <small class="text-muted text-nowrap">${relativeTime(n.time)}</small>
      </div>`
  }).join('')

  updateBadge(notifications.length)
}

function updateBadge(count: number): void {
  const badge = document.querySelector('.notifications-dropdown .badge')
  if (!badge) return
  if (count > 0) {
    badge.textContent = String(count)
    badge.classList.remove('d-none')
  } else {
    badge.textContent = ''
    badge.classList.add('d-none')
  }
}

function escapeHtml(str: string): string {
  const div = document.createElement('div')
  div.textContent = str
  return div.innerHTML
}

async function refresh(): Promise<void> {
  const [notifications, prefs] = await Promise.all([fetchNotifications(), fetchPrefs()])

  // Filter by user preferences (default all enabled)
  const filtered = notifications.filter(n => {
    const key = FAIL_TYPE_KEYS[n.fail_type]
    return key ? prefs[key as keyof NotificationPrefs] !== false : true
  })

  renderNotifications(filtered)
}

export function initNotificationDropdown(): void {
  // Clean up previous timer (SPA navigation)
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }

  // Initial fetch
  refresh()

  // Poll every 60 seconds
  pollTimer = setInterval(refresh, 60_000)
}
