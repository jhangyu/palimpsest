/* global fetch */
const API_BASE = import.meta.env.DEV ? 'http://localhost:8088' : ''

// --- Auth Types ---

export interface AuthUser {
  id: number
  email: string
  username: string
  full_name: string | null
  status: string
  roles: string[]
  email_verified_at: string | null
  avatar_source: string
  preferences: Record<string, unknown>
  created_at: string
  last_login_at: string | null
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  username: string
  password: string
  full_name?: string
}

export interface ForgotPasswordRequest {
  email: string
}

export interface ResetPasswordRequest {
  token: string
  password: string
}

// --- Site Types ---

export interface Site {
  id: number
  name: string
  url: string
  refresh_frequency: number
  list_rules: Record<string, unknown>
  content_rules: Record<string, unknown>
  scrape_method?: string
  consecutive_failure_count?: number
}

export interface AnalyzeResult {
  rules: Record<string, unknown> | null
  debug_dir?: string
  error?: string
}

export interface PreviewItem {
  title: string
  url?: string
  published_at?: string
  content?: string
}

export interface PreviewResult {
  status: string
  data: PreviewItem[]
  debug_dir?: string
}

export interface CreateSitePayload {
  site: {
    url: string
    name: string
    refresh_frequency: number
    scrape_method?: string
  }
  rules: {
    list_rules: Record<string, unknown>
    content_rules: Record<string, unknown>
  }
}

export interface CreateSiteResponse {
  id: number
  status: string
}

export interface PreviewCrawlPayload {
  url: string
  list_rules: Record<string, unknown>
  content_rules: Record<string, unknown>
  mode?: string
  target_url?: string
  scrape_method?: string
}

// --- Articles Types ---

export interface ArticleListItem {
  article_title: string
  image_url: string | null
  feed_name: string
  word_count: number
  update_time: string
  ori_url: string
  author: string | null
}

export interface ArticleListResponse {
  articles: ArticleListItem[]
  filter_counts: { today: number; week: number; month: number; all: number }
  total: number
  page: number
  page_size: number
}

// --- User Profile Types ---

export interface UserProfile {
  id: number
  email: string
  username: string
  full_name: string | null
  status: string
  roles: string[]
  email_verified_at: string | null
  pending_email: string | null
  avatar_source: string
  preferences: Record<string, unknown>
  created_at: string
  updated_at: string
  last_login_at: string | null
}

export type AdminUser = UserProfile

export interface AdminUserList {
  users: AdminUser[]
  total: number
  page: number
  page_size: number
  per_page?: number
}

export interface Role {
  id: number
  name: string
  description: string | null
  user_count: number
}

// --- Analytics Types ---

export interface AnalyticsSummary {
  total_article_scrap: number
  new_articles_last_week: number
  new_articles_this_week: number
  new_articles_weekly_change_pct: number | null
  median_feed_update_minutes: number | null
  median_feed_update_change_pct: number | null
  median_article_word_count: number | null
  median_article_word_count_trend_label: string
}

export interface ChartDataset {
  label: string
  data: number[]
  color?: string
}

export interface ChartData {
  labels: string[]
  datasets: ChartDataset[]
}

export interface FeedsDistributionItem {
  name: string
  value: number
  color: string
}

export interface FeedsDistribution {
  items: FeedsDistributionItem[]
}

export interface TrafficMetrics {
  rss_query: ChartData
  article_scrap: ChartData
}

export interface LatestArticle {
  feed_name: string
  article_title: string
  update_time: string
  word_count: number
  ori_url: string
}

export interface AnalyticsOverview {
  summary: AnalyticsSummary
  articles_counts_overview: ChartData
  feeds_distribution: FeedsDistribution
  traffic_metrics: TrafficMetrics
  article_growth: ChartData
  daily_rss_query: ChartData
  latest_articles: LatestArticle[]
}

// --- CSRF Helper ---

/**
 * Read the csrf_token cookie value set by the server.
 * Returns empty string if not present (unauthenticated or not yet set).
 */
function getCsrfToken(): string {
  const match = document.cookie
    .split('; ')
    .find((row) => row.startsWith('csrf_token='))
  return match ? decodeURIComponent(match.split('=')[1]) : ''
}

/**
 * Build headers for state-changing requests (POST/PUT/PATCH/DELETE).
 * Always includes Content-Type: application/json and X-CSRF-Token when available.
 */
function stateChangingHeaders(extra: Record<string, string> = {}): HeadersInit {
  const csrfToken = getCsrfToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...extra
  }
  if (csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }
  return headers
}

/**
 * Build headers with only the CSRF token — no Content-Type.
 * Use for FormData requests where the browser sets the multipart boundary automatically.
 */
function csrfHeader(): Record<string, string> {
  const csrfToken = getCsrfToken()
  const headers: Record<string, string> = {}
  if (csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }
  return headers
}

// --- Error Handling ---

async function throwOnError(res: Response): Promise<void> {
  if (!res.ok) {
    // 401 → redirect to login
    if (res.status === 401) {
      const currentPath = window.location.pathname
      const loginPath = '/authentication/modern/login'
      if (currentPath !== loginPath) {
        window.location.href = loginPath
      }
      // Throw so callers can break out of any pending logic
      throw new Error('Unauthorized')
    }

    let detail: string
    try {
      const body = await res.json()
      detail = body.detail || `HTTP ${res.status}`
    } catch {
      detail = `HTTP ${res.status}`
    }
    throw new Error(detail)
  }
}

export const api = {
  // --- Auth Methods ---

  login: async (data: LoginRequest): Promise<AuthUser> => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(data)
    })
    await throwOnError(res)
    return res.json()
  },

  logout: async (): Promise<void> => {
    const res = await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      headers: stateChangingHeaders(),
      credentials: 'include'
    })
    await throwOnError(res)
  },

  getMe: async (): Promise<AuthUser> => {
    const res = await fetch(`${API_BASE}/auth/me`, {
      credentials: 'include'
    })
    await throwOnError(res)
    return res.json()
  },

  register: async (data: RegisterRequest): Promise<AuthUser> => {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(data)
    })
    await throwOnError(res)
    return res.json()
  },

  forgotPassword: async (data: ForgotPasswordRequest): Promise<void> => {
    const res = await fetch(`${API_BASE}/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(data)
    })
    await throwOnError(res)
  },

  resetPassword: async (data: ResetPasswordRequest): Promise<void> => {
    const res = await fetch(`${API_BASE}/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(data)
    })
    await throwOnError(res)
  },

  // --- Site Methods ---

  getSites: async (): Promise<Site[]> => {
    const res = await fetch(`${API_BASE}/sites/`, {
      credentials: 'include'
    })
    await throwOnError(res)
    return res.json()
  },

  getSite: async (id: number): Promise<Site> => {
    const res = await fetch(`${API_BASE}/sites/${id}`, {
      credentials: 'include'
    })
    await throwOnError(res)
    return res.json()
  },

  deleteSite: async (id: number): Promise<void> => {
    const res = await fetch(`${API_BASE}/sites/${id}`, {
      method: 'DELETE',
      headers: stateChangingHeaders(),
      credentials: 'include'
    })
    await throwOnError(res)
  },

  updateSite: async (id: number, payload: Partial<Site>): Promise<void> => {
    const res = await fetch(`${API_BASE}/sites/${id}`, {
      method: 'PUT',
      headers: stateChangingHeaders(),
      credentials: 'include',
      body: JSON.stringify(payload)
    })
    await throwOnError(res)
  },

  duplicateSite: async (id: number): Promise<void> => {
    const res = await fetch(`${API_BASE}/sites/${id}/duplicate`, {
      method: 'POST',
      headers: stateChangingHeaders(),
      credentials: 'include'
    })
    await throwOnError(res)
  },

  triggerCrawl: async (id: number, debug = false): Promise<void> => {
    const params = debug ? `?debug=true` : ''
    const res = await fetch(`${API_BASE}/crawl/${id}${params}`, {
      method: 'POST',
      headers: stateChangingHeaders(),
      credentials: 'include'
    })
    await throwOnError(res)
  },

  analyzeList: async (url: string, debug = false): Promise<AnalyzeResult> => {
    const debugParam = debug ? '&debug=true' : ''
    const res = await fetch(
      `${API_BASE}/analyze/list?url=${encodeURIComponent(url)}${debugParam}`,
      {
        method: 'POST',
        headers: stateChangingHeaders(),
        credentials: 'include'
      }
    )
    await throwOnError(res)
    const data = await res.json()
    if (data.error) throw new Error(data.error)
    if (!data.rules) throw new Error('AI analysis returned no rules')
    return data as AnalyzeResult
  },

  analyzeContent: async (
    url: string,
    debug = false
  ): Promise<AnalyzeResult> => {
    const debugParam = debug ? '&debug=true' : ''
    const res = await fetch(
      `${API_BASE}/analyze/content?url=${encodeURIComponent(url)}${debugParam}`,
      {
        method: 'POST',
        headers: stateChangingHeaders(),
        credentials: 'include'
      }
    )
    await throwOnError(res)
    const data = await res.json()
    if (data.error) throw new Error(data.error)
    if (!data.rules) throw new Error('AI analysis returned no rules')
    return data as AnalyzeResult
  },

  createSite: async (payload: CreateSitePayload): Promise<CreateSiteResponse> => {
    const res = await fetch(`${API_BASE}/sites/`, {
      method: 'POST',
      headers: stateChangingHeaders(),
      credentials: 'include',
      body: JSON.stringify(payload)
    })
    await throwOnError(res)
    return res.json()
  },

  previewCrawl: async (
    payload: PreviewCrawlPayload,
    debug = false
  ): Promise<PreviewResult> => {
    const res = await fetch(`${API_BASE}/crawl/preview`, {
      method: 'POST',
      headers: stateChangingHeaders(),
      credentials: 'include',
      body: JSON.stringify({ ...payload, debug })
    })
    await throwOnError(res)
    return res.json()
  },

  getAnalyticsOverview: async (days = 30): Promise<AnalyticsOverview> => {
    const res = await fetch(`${API_BASE}/analytics/overview?days=${days}`, {
      credentials: 'include'
    })
    await throwOnError(res)
    return res.json()
  },

  getArticlesList: async (filter = 'all', search = '', page = 1, pageSize = 100): Promise<ArticleListResponse> => {
    const params = new URLSearchParams({ filter, search, page: String(page), page_size: String(pageSize) })
    const res = await fetch(`${API_BASE}/articles/list?${params}`, {
      credentials: 'include'
    })
    await throwOnError(res)
    return res.json()
  },

  // --- User Profile Methods ---

  getProfile: async (): Promise<UserProfile> => {
    const res = await fetch(`${API_BASE}/users/me`, {
      credentials: 'include'
    })
    await throwOnError(res)
    return res.json()
  },

  updateProfile: async (data: Partial<Pick<UserProfile, 'full_name'>>): Promise<UserProfile> => {
    const res = await fetch(`${API_BASE}/users/me`, {
      method: 'PUT',
      headers: stateChangingHeaders(),
      credentials: 'include',
      body: JSON.stringify(data)
    })
    await throwOnError(res)
    return res.json()
  },

  updateEmail: async (data: { new_email: string; password: string }): Promise<void> => {
    const res = await fetch(`${API_BASE}/users/me/email`, {
      method: 'PUT',
      headers: stateChangingHeaders(),
      credentials: 'include',
      body: JSON.stringify(data)
    })
    await throwOnError(res)
  },

  updateUsername: async (data: { new_username: string }): Promise<void> => {
    const res = await fetch(`${API_BASE}/users/me/username`, {
      method: 'PUT',
      headers: stateChangingHeaders(),
      credentials: 'include',
      body: JSON.stringify(data)
    })
    await throwOnError(res)
  },

  changePassword: async (data: { current_password: string; new_password: string }): Promise<void> => {
    const res = await fetch(`${API_BASE}/users/me/password`, {
      method: 'PUT',
      headers: stateChangingHeaders(),
      credentials: 'include',
      body: JSON.stringify(data)
    })
    await throwOnError(res)
  },

  updatePreferences: async (data: Record<string, unknown>): Promise<void> => {
    const res = await fetch(`${API_BASE}/users/me/preferences`, {
      method: 'PUT',
      headers: stateChangingHeaders(),
      credentials: 'include',
      body: JSON.stringify({ preferences: data })
    })
    await throwOnError(res)
  },

  uploadAvatar: async (file: File): Promise<void> => {
    const formData = new FormData()
    formData.append('file', file)
    const csrfToken = document.cookie
      .split('; ')
      .find((row) => row.startsWith('csrf_token='))
    const headers: Record<string, string> = {}
    if (csrfToken) {
      headers['X-CSRF-Token'] = decodeURIComponent(csrfToken.split('=')[1])
    }
    const res = await fetch(`${API_BASE}/users/me/avatar`, {
      method: 'PUT',
      headers,
      credentials: 'include',
      body: formData
    })
    await throwOnError(res)
  },

  deleteAvatar: async (): Promise<void> => {
    const res = await fetch(`${API_BASE}/users/me/avatar`, {
      method: 'DELETE',
      headers: stateChangingHeaders(),
      credentials: 'include'
    })
    await throwOnError(res)
  },

  getAvatarUrl: (): string => {
    return `${API_BASE}/users/me/avatar`
  },

  setAvatarSource: async (source: 'none' | 'gravatar'): Promise<void> => {
    const res = await fetch(`${API_BASE}/users/me/avatar-source`, {
      method: 'PUT',
      credentials: 'include',
      headers: stateChangingHeaders(),
      body: JSON.stringify({ source })
    })
    await throwOnError(res)
  },

  // --- Admin User Methods ---

  adminListUsers: async (page = 1, perPage = 20, search = ''): Promise<AdminUserList> => {
    const params = new URLSearchParams({ page: String(page), page_size: String(perPage) })
    if (search) params.set('search', search)
    const res = await fetch(`${API_BASE}/admin/users?${params}`, {
      credentials: 'include'
    })
    await throwOnError(res)
    const data = await res.json()
    return { ...data, per_page: data.per_page ?? data.page_size }
  },

  adminCreateUser: async (data: { email: string; username: string; full_name?: string; roles?: string[] }): Promise<AdminUser> => {
    const res = await fetch(`${API_BASE}/admin/users`, {
      method: 'POST',
      headers: stateChangingHeaders(),
      credentials: 'include',
      body: JSON.stringify(data)
    })
    await throwOnError(res)
    return res.json()
  },

  adminGetUser: async (id: number): Promise<AdminUser> => {
    const res = await fetch(`${API_BASE}/admin/users/${id}`, {
      credentials: 'include'
    })
    await throwOnError(res)
    return res.json()
  },

  adminUpdateUser: async (id: number, data: Partial<Pick<AdminUser, 'email' | 'username' | 'full_name' | 'status'>>): Promise<AdminUser> => {
    const res = await fetch(`${API_BASE}/admin/users/${id}`, {
      method: 'PUT',
      headers: stateChangingHeaders(),
      credentials: 'include',
      body: JSON.stringify(data)
    })
    await throwOnError(res)
    return res.json()
  },

  adminDeleteUser: async (id: number): Promise<void> => {
    const res = await fetch(`${API_BASE}/admin/users/${id}`, {
      method: 'DELETE',
      headers: stateChangingHeaders(),
      credentials: 'include'
    })
    await throwOnError(res)
  },

  adminUpdateRoles: async (id: number, roleIds: number[]): Promise<void> => {
    const res = await fetch(`${API_BASE}/admin/users/${id}/roles`, {
      method: 'PUT',
      headers: stateChangingHeaders(),
      credentials: 'include',
      body: JSON.stringify({ role_ids: roleIds })
    })
    await throwOnError(res)
  },

  listRoles: async (): Promise<Role[]> => {
    const res = await fetch(`${API_BASE}/admin/roles`, {
      credentials: 'include'
    })
    await throwOnError(res)
    const data = await res.json()
    return Array.isArray(data) ? data : (data.roles ?? [])
  },

  // --- Database Management Methods ---

  getDatabaseStatus: async (): Promise<{
    schema_version: string
    app_version: string
    tables: { name: string; row_count: number }[]
    pending_migrations: { version: string; description: string }[]
    last_migration_at: string | null
  }> => {
    const res = await fetch(`${API_BASE}/settings/database/status`, {
      credentials: 'include'
    })
    await throwOnError(res)
    return res.json()
  },

  runMigrations: async (): Promise<{
    applied: { version: string; description: string }[]
  }> => {
    const res = await fetch(`${API_BASE}/settings/database/migrate`, {
      method: 'POST',
      credentials: 'include',
      headers: stateChangingHeaders()
    })
    await throwOnError(res)
    return res.json()
  },

  exportDatabase: async (tables: string[], format: 'json' | 'zip' = 'zip'): Promise<void> => {
    const params = new URLSearchParams()
    params.set('tables', tables.join(','))
    params.set('format', format)
    const res = await fetch(`${API_BASE}/settings/database/export?${params}`, {
      credentials: 'include'
    })
    await throwOnError(res)
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const date = new Date().toISOString().slice(0, 10)
    const ext = format === 'zip' ? 'zip' : 'json'
    a.href = url
    a.download = `palimpsest-export-${date}.${ext}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  },

  previewImport: async (file: File): Promise<{
    compatible: boolean
    warnings: string[]
    tables: { name: string; total: number; new: number; conflicts: number }[]
  }> => {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${API_BASE}/settings/database/import/preview`, {
      method: 'POST',
      credentials: 'include',
      headers: csrfHeader(),
      body: form
    })
    await throwOnError(res)
    return res.json()
  },

  importDatabase: async (file: File, mode: 'skip' | 'overwrite'): Promise<{
    tables: { name: string; imported: number; skipped: number; overwritten: number }[]
  }> => {
    const form = new FormData()
    form.append('file', file)
    const params = new URLSearchParams({ mode })
    const res = await fetch(`${API_BASE}/settings/database/import?${params}`, {
      method: 'POST',
      credentials: 'include',
      headers: csrfHeader(),
      body: form
    })
    await throwOnError(res)
    return res.json()
  }
}
