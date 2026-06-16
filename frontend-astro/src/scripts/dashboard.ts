import { api, type Site } from '@/scripts/api'
import { escapeHtml, escapeAttr } from '@/scripts/utils'

function normalizeUrl(name: string): string {
  return name
    .replace(/ /g, '_')
    .replace(/[^a-zA-Z0-9_-]/g, '')
    .toLowerCase()
}

function renderMetricCards(container: HTMLElement, sites: Site[]): void {
  container.innerHTML = `
    <div class="col-xl-4 col-md-6">
      <div class="small-box text-bg-primary">
        <div class="inner">
          <h3 class="text-white fw-bold">${sites.length}</h3>
          <p class="text-white fw-bold">Total Feeds</p>
        </div>
        <div class="small-box-icon">
          <i class="ri-rss-line"></i>
        </div>
        <a href="/feeds/add" class="small-box-footer text-white fw-bold">
          Add Feed <i class="ri-arrow-right-line"></i>
        </a>
      </div>
    </div>
    <div class="col-xl-4 col-md-6">
      <div class="small-box text-bg-success">
        <div class="inner">
          <h3 class="text-white fw-bold">Healthy</h3>
          <p class="text-white fw-bold">System Status</p>
        </div>
        <div class="small-box-icon">
          <i class="ri-heart-pulse-line"></i>
        </div>
        <a href="#" class="small-box-footer text-white fw-bold">
          View Details <i class="ri-arrow-right-line"></i>
        </a>
      </div>
    </div>
    <div class="col-xl-4 col-md-6">
      <div class="small-box text-bg-info">
        <div class="inner">
          <h3 class="text-white fw-bold">3</h3>
          <p class="text-white fw-bold">Active Services</p>
        </div>
        <div class="small-box-icon">
          <i class="ri-stack-line"></i>
        </div>
        <a href="#" class="small-box-footer text-white fw-bold">
          View Details <i class="ri-arrow-right-line"></i>
        </a>
      </div>
    </div>
  `
}

function renderFeedTable(container: HTMLElement, sites: Site[]): void {
  if (sites.length === 0) {
    container.innerHTML = `
      <p class="text-muted text-center py-4">
        No feeds found. <a href="/feeds/add">Create one!</a>
      </p>
    `
    return
  }

  const rows = sites
    .map((site) => {
      const rssUrl = `/rss/${normalizeUrl(site.name)}`
      const freq = site.refresh_frequency || 60
      const freqDisplay = freq >= 60 ? `${Math.round(freq / 60 * 10) / 10}h` : `${freq}min`
      return `
      <tr>
        <td>
          <div class="fw-semibold">${escapeHtml(site.name)}</div>
        </td>
        <td>
          <a href="${escapeAttr(site.url)}" target="_blank" rel="noopener noreferrer" class="text-truncate d-inline-block" style="max-width: 300px;">
            ${escapeHtml(site.url)}
          </a>
        </td>
        <td>
          <span class="badge text-bg-light text-dark">Every ${freqDisplay}</span>
        </td>
        <td>
          <div class="d-flex gap-1">
            <a href="/feeds/edit?site=${site.id}" class="btn btn-sm btn-outline-secondary" title="Edit">
              <i class="ri-settings-3-line"></i>
            </a>
            <button class="btn btn-sm btn-outline-secondary" data-action="copy-rss" data-rss-url="${escapeAttr(rssUrl)}" title="Copy RSS URL">
              <i class="ri-clipboard-line"></i>
            </button>
            <button class="btn btn-sm btn-outline-secondary" data-action="trigger-crawl" data-site-id="${site.id}" title="Trigger Crawl">
              <i class="ri-refresh-line"></i>
            </button>
            <button class="btn btn-sm btn-outline-danger" data-action="delete-site" data-site-id="${site.id}" data-site-name="${escapeHtml(site.name)}" title="Delete">
              <i class="ri-delete-bin-line"></i>
            </button>
          </div>
        </td>
      </tr>`
    })
    .join('')

  container.innerHTML = `
    <div class="table-responsive">
      <table class="table table-hover align-middle mb-0">
        <thead>
          <tr>
            <th>Name</th>
            <th>URL</th>
            <th>Refresh Frequency</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    </div>
  `
}

function showToast(message: string, variant: 'success' | 'danger' = 'success'): void {
  const toast = document.createElement('div')
  toast.className = `alert alert-${variant} position-fixed bottom-0 end-0 m-3`
  toast.style.zIndex = '9999'
  toast.textContent = message
  document.body.appendChild(toast)
  setTimeout(() => toast.remove(), 3000)
}

function bindActions(feedTableContainer: HTMLElement, onRefresh: () => void): void {
  feedTableContainer.addEventListener('click', async (e) => {
    const target = (e.target as HTMLElement).closest<HTMLElement>('[data-action]')
    if (!target) return

    const action = target.dataset.action

    if (action === 'copy-rss') {
      const rssUrl = target.dataset.rssUrl || ''
      const fullUrl = `${window.location.origin}${rssUrl}`
      try {
        await navigator.clipboard.writeText(fullUrl)
        showToast('RSS URL copied to clipboard!')
      } catch {
        showToast('Failed to copy URL', 'danger')
      }
    }

    if (action === 'trigger-crawl') {
      const siteId = Number(target.dataset.siteId)
      target.classList.add('disabled')
      try {
        await api.triggerCrawl(siteId)
        showToast('Crawl triggered successfully!')
      } catch {
        showToast('Failed to trigger crawl', 'danger')
      } finally {
        target.classList.remove('disabled')
      }
    }

    if (action === 'delete-site') {
      const siteId = Number(target.dataset.siteId)
      const siteName = target.dataset.siteName || ''
      if (!window.confirm(`Are you sure you want to delete "${siteName}"?`)) return
      try {
        await api.deleteSite(siteId)
        showToast('Feed deleted successfully!')
        onRefresh()
      } catch {
        showToast('Failed to delete feed', 'danger')
      }
    }
  })
}

export async function initDashboard(): Promise<void> {
  const metricsContainer = document.getElementById('dashboard-metrics')
  if (!metricsContainer || metricsContainer.dataset.inited) return
  metricsContainer.dataset.inited = 'true'

  const feedTableContainer = document.getElementById('dashboard-feed-table')

  if (!feedTableContainer) return

  // Show loading state
  feedTableContainer.innerHTML = `
    <div class="text-center py-4">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Loading...</span>
      </div>
      <p class="text-muted mt-2">Loading feeds...</p>
    </div>
  `

  const loadData = async () => {
    try {
      const sites = await api.getSites()
      renderMetricCards(metricsContainer, sites)
      renderFeedTable(feedTableContainer, sites)
    } catch (err) {
      console.error('Failed to load dashboard data:', err)
      feedTableContainer.innerHTML = `
        <div class="alert alert-danger" role="alert">
          <i class="ri-error-warning-line me-2"></i>
          Failed to load feeds. Please check the API connection and try again.
        </div>
      `
    }
  }

  bindActions(feedTableContainer, loadData)
  await loadData()
}
