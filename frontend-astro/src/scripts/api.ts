/*
---
name: api
description: "Central typed API client: CSRF-aware fetch wrapper, cache integration, and typed methods for all backend endpoints (auth, sites, analytics, users, admin, database)"
type: script
target:
  layer: frontend
  domain: api-client
spec_doc: null
test_file: null
functions:
  - name: getCsrfToken
    line: 338
    purpose: "Read csrf_token cookie value set by the server"
  - name: stateChangingHeaders
    line: 349
    purpose: "Build headers with Content-Type and X-CSRF-Token for state-changing requests"
  - name: csrfHeader
    line: 365
    purpose: "Build CSRF-only headers (no Content-Type) for FormData multipart requests"
  - name: throwOnError
    line: 376
    purpose: "Assert response is OK; redirect to login on 401, throw structured error on failure"
  - name: api.login
    line: 409
    purpose: "POST /auth/login — authenticate user and return AuthUser"
  - name: api.logout
    line: 420
    purpose: "POST /auth/logout — terminate current session"
  - name: api.getMe
    line: 429
    purpose: "GET /auth/me — fetch current authenticated user"
  - name: api.getSites
    line: 470
    purpose: "GET /sites/ — list all sites with in-memory TTL cache"
  - name: api.createSite
    line: 568
    purpose: "POST /sites/ — create new site with list/content rules payload"
  - name: api.previewCrawl
    line: 580
    purpose: "POST /crawl/preview — preview crawl results with given rules"
  - name: api.getAnalyticsOverview
    line: 594
    purpose: "GET /analytics/overview — fetch analytics summary and chart data"
  - name: api.getDatabaseStatus
    line: 788
    purpose: "GET /settings/database/status — fetch DB schema version and migration state"
  - name: api.exportDatabase
    line: 814
    purpose: "GET /settings/database/export — trigger file download of exported tables"
  - name: api.importDatabase
    line: 852
    purpose: "POST /settings/database/import — import database file with skip or overwrite conflict mode"
---
*/
/* global fetch */
import { getCached, setCache, invalidateCache } from '@/scripts/cache'

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

// --- Filter Types ---

export interface FilterRule {
  id: string
  type: 'rule'
  field: 'title' | 'content' | 'title_content'
  match: 'contains' | 'not_contains' | 'equals' | 'starts_with' | 'ends_with' | 'regex'
  value: string
}

export interface FilterGroup {
  id: string
  type: 'group'
  operator: 'and' | 'or'
  children: (FilterRule | FilterGroup)[]
}

export interface FilterConfig {
  mode: 'blacklist' | 'whitelist'
  match_whole_word: boolean
  root: FilterGroup
}

// --- Site Types ---

export type RefreshFrequencyMode = 'manual' | 'auto'

export interface Site {
  id: number
  name: string
  url: string
  refresh_frequency: number
  refresh_frequency_mode?: RefreshFrequencyMode
  auto_refresh_frequency_minutes?: number | null
  next_crawl_at?: string | null
  last_crawled_at?: string | null
  list_rules: Record<string, unknown>
  content_rules: Record<string, unknown>
  filter_rules?: FilterConfig | null
  scrape_method?: string
  consecutive_failure_count?: number
  source_type?: 'html' | 'rss'
  rss_full_content?: boolean
  website_url?: string
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
  filtered?: boolean
}

export interface PreviewResult {
  status: string
  data: PreviewItem[]
  debug_dir?: string
  filter_summary?: {
    passed: number
    filtered_out: number
  }
}

export interface CreateSitePayload {
  site: {
    url: string
    name: string
    refresh_frequency: number
    refresh_frequency_mode?: RefreshFrequencyMode
    auto_refresh_frequency_minutes?: number | null
    scrape_method?: string
    source_type?: 'html' | 'rss'
    rss_full_content?: boolean
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
  filter_rules?: FilterConfig | null
  mode?: string
  target_url?: string
  scrape_method?: string
  source_type?: 'html' | 'rss'
}

export interface FeedParseResponse {
  success: boolean
  feed_title?: string
  feed_link?: string
  item_count: number
  has_full_content: boolean
  items: Array<{
    title: string
    url: string
    pub_date?: string
    author?: string
  }>
}

// --- Articles Types ---

export interface ArticleListItem {
  article_title: string
  image_url: string | null
  feed_name: string
  word_count: number
  published_at: string
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
  published_at: string
  word_count: number
  ori_url: string
}

export interface FeedEventItem {
  rank: number
  feed_name: string
  site_id: number
  count: number
  percentage: number
}

export interface FailedCrawlItem {
  rank: number
  feed_name: string
  site_id: number
  task_failures: number
  article_failures: number
  percentage: number
}

export interface FeedEvents {
  new_articles: FeedEventItem[]
  failed_crawls: FailedCrawlItem[]
  ai_repairs: FeedEventItem[]
  fetch_failures: FeedEventItem[]
}

export interface EventSummary {
  new_articles: number
  failed_crawls: number
  ai_repairs: number
  fetch_failures: number
}

export interface AnalyticsOverview {
  summary: AnalyticsSummary
  articles_counts_overview: ChartData
  feeds_distribution: FeedsDistribution
  traffic_metrics: TrafficMetrics
  article_growth: ChartData
  daily_rss_query: ChartData
  latest_articles: LatestArticle[]
  feed_events: FeedEvents
  event_summary: EventSummary
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

async function throwOnError(res: Response, options?: { skipRedirectOn401?: boolean }): Promise<void> {
  if (!res.ok) {
    // 401 → redirect to login (unless caller opts out, e.g. password verification endpoints)
    if (res.status === 401 && !options?.skipRedirectOn401) {
      const currentPath = window.location.pathname
      const pagesPrefix = (import.meta as ImportMeta).env.DEV ? '' : '/pages'
      const loginPath = `${pagesPrefix}/authentication/modern/login`
      if (currentPath !== loginPath) {
        window.location.href = loginPath
      }
      // Throw so callers can break out of any pending logic
      throw new Error('Unauthorized')
    }

    let detail: string
    try {
      const body = await res.json()
      if (Array.isArray(body.detail)) {
        // FastAPI validation errors return an array of objects
        detail = body.detail.map((e: { msg: string }) => e.msg).join('; ')
      } else {
        detail = body.detail || `HTTP ${res.status}`
      }
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
    const cached = getCached<Site[]>('sites')
    if (cached) return cached
    const res = await fetch(`${API_BASE}/sites/`, {
      credentials: 'include'
    })
    await throwOnError(res)
    const data: Site[] = await res.json()
    setCache('sites', data)
    return data
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
    invalidateCache('sites')
  },

  updateSite: async (id: number, payload: Partial<Site>): Promise<void> => {
    const res = await fetch(`${API_BASE}/sites/${id}`, {
      method: 'PUT',
      headers: stateChangingHeaders(),
      credentials: 'include',
      body: JSON.stringify(payload)
    })
    await throwOnError(res)
    invalidateCache('sites')
  },

  duplicateSite: async (id: number): Promise<void> => {
    const res = await fetch(`${API_BASE}/sites/${id}/duplicate`, {
      method: 'POST',
      headers: stateChangingHeaders(),
      credentials: 'include'
    })
    await throwOnError(res)
    invalidateCache('sites')
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

  forceRefresh: async (siteId: number, scope: 'current' | 'all_db'): Promise<void> => {
    const res = await fetch(`${API_BASE}/sites/${siteId}/force-refresh`, {
      method: 'POST',
      headers: stateChangingHeaders(),
      credentials: 'include',
      body: JSON.stringify({ scope })
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
    invalidateCache('sites')
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
    // 401 here means wrong current password, not session expired — don't redirect
    await throwOnError(res, { skipRedirectOn401: true })
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
  },

  parseFeed: async (url: string): Promise<FeedParseResponse> => {
    const res = await fetch(`${API_BASE}/feed/parse`, {
      method: 'POST',
      headers: stateChangingHeaders(),
      credentials: 'include',
      body: JSON.stringify({ url })
    })
    await throwOnError(res)
    return res.json()
  }
}
