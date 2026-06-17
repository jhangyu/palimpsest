/* global fetch */
const API_BASE = import.meta.env.DEV ? 'http://localhost:8088' : ''

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

async function throwOnError(res: Response): Promise<void> {
  if (!res.ok) {
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
  getSites: async (): Promise<Site[]> => {
    const res = await fetch(`${API_BASE}/sites/`)
    await throwOnError(res)
    return res.json()
  },

  getSite: async (id: number): Promise<Site> => {
    const res = await fetch(`${API_BASE}/sites/${id}`)
    await throwOnError(res)
    return res.json()
  },

  deleteSite: async (id: number): Promise<void> => {
    const res = await fetch(`${API_BASE}/sites/${id}`, { method: "DELETE" })
    await throwOnError(res)
  },

  updateSite: async (id: number, payload: Partial<Site>): Promise<void> => {
    const res = await fetch(`${API_BASE}/sites/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
    await throwOnError(res)
  },

  duplicateSite: async (id: number): Promise<void> => {
    const res = await fetch(`${API_BASE}/sites/${id}/duplicate`, {
      method: "POST"
    })
    await throwOnError(res)
  },

  triggerCrawl: async (id: number, debug = false): Promise<void> => {
    const params = debug ? `?debug=true` : ""
    const res = await fetch(`${API_BASE}/crawl/${id}${params}`, {
      method: "POST"
    })
    await throwOnError(res)
  },

  analyzeList: async (url: string, debug = false): Promise<AnalyzeResult> => {
    const debugParam = debug ? "&debug=true" : ""
    const res = await fetch(
      `${API_BASE}/analyze/list?url=${encodeURIComponent(url)}${debugParam}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" }
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
    const debugParam = debug ? "&debug=true" : ""
    const res = await fetch(
      `${API_BASE}/analyze/content?url=${encodeURIComponent(url)}${debugParam}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" }
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
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, debug })
    })
    await throwOnError(res)
    return res.json()
  },

  getAnalyticsOverview: async (days = 30): Promise<AnalyticsOverview> => {
    const res = await fetch(`${API_BASE}/analytics/overview?days=${days}`)
    await throwOnError(res)
    return res.json()
  },

  getArticlesList: async (filter = 'all', search = '', page = 1, pageSize = 100): Promise<ArticleListResponse> => {
    const params = new URLSearchParams({ filter, search, page: String(page), page_size: String(pageSize) })
    const res = await fetch(`${API_BASE}/articles/list?${params}`)
    await throwOnError(res)
    return res.json()
  }
}
