/**
 * Analytics page runtime: fetches /analytics/overview and populates
 * info-boxes, charts, and the latest-articles table.
 */
import { api } from './api'
import type { AnalyticsOverview } from './api'
import { updateChart } from './charts'

// --- Formatting helpers ---

function fmtNumber(n: number | null | undefined): string {
  if (n == null) return '—'
  return n.toLocaleString('en-US')
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return ''
  const sign = n >= 0 ? '+' : ''
  return `${sign}${n}%`
}

function fmtMinutes(n: number | null | undefined): string {
  if (n == null) return '—'
  if (n < 60) return `${Math.round(n)}m`
  const h = Math.floor(n / 60)
  const m = Math.round(n % 60)
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}

function fmtWordCount(n: number | null | undefined): string {
  if (n == null) return '—'
  return n.toLocaleString('en-US')
}

function truncateUrl(url: string, max = 40): string {
  if (url.length <= max) return url
  return url.slice(0, max - 1) + '…'
}

function fmtTime(iso: string): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-TW', { timeZone: 'Asia/Taipei', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso.slice(0, 16)
  }
}

// --- DOM helpers ---

function setText(id: string, text: string) {
  const el = document.getElementById(id)
  if (el) el.textContent = text
}


function showEl(id: string, show: boolean) {
  const el = document.getElementById(id)
  if (el) el.style.display = show ? '' : 'none'
}

// --- Main init ---

export async function initAnalytics() {
  showEl('analyticsLoadingState', true)
  showEl('analyticsErrorState', false)

  try {
    const data: AnalyticsOverview = await api.getAnalyticsOverview(30)
    showEl('analyticsLoadingState', false)
    populateSummary(data)
    populateCharts(data)
    populateLatestArticles(data)
  } catch (err) {
    showEl('analyticsLoadingState', false)
    showEl('analyticsErrorState', true)
    const errEl = document.getElementById('analyticsErrorState')
    if (errEl) errEl.textContent = `Failed to load analytics: ${err instanceof Error ? err.message : String(err)}`
    console.error('[Analytics] Load error:', err)
  }
}

function populateSummary(data: AnalyticsOverview) {
  const s = data.summary

  // Total Article Scrap
  setText('analytics-total-article-scrap', fmtNumber(s.total_article_scrap))
  setText('analytics-total-article-scrap-trend', `${fmtNumber(s.new_articles_last_week)} new articles from last week`)

  // New Articles This Week
  setText('analytics-new-articles-week', fmtNumber(s.new_articles_this_week))
  const weekTrendEl = document.getElementById('analytics-new-articles-week-trend')
  if (weekTrendEl) {
    if (s.new_articles_weekly_change_pct != null) {
      const isUp = s.new_articles_weekly_change_pct >= 0
      weekTrendEl.innerHTML = `<i class="ri-arrow-${isUp ? 'up' : 'down'}-line"></i> ${fmtPct(s.new_articles_weekly_change_pct)} from last week`
      weekTrendEl.className = `info-box-trend ${isUp ? '' : 'text-danger'}`
    } else {
      weekTrendEl.textContent = 'Not enough data'
    }
  }

  // Median Feed Update
  setText('analytics-median-feed-update', fmtMinutes(s.median_feed_update_minutes))
  const feedTrendEl = document.getElementById('analytics-median-feed-update-trend')
  if (feedTrendEl) {
    if (s.median_feed_update_change_pct != null) {
      const isDecrease = s.median_feed_update_change_pct <= 0
      feedTrendEl.innerHTML = `<i class="ri-arrow-${isDecrease ? 'down' : 'up'}-line"></i> ${fmtPct(Math.abs(s.median_feed_update_change_pct))} from last week`
      feedTrendEl.className = `info-box-trend ${isDecrease ? '' : 'text-danger'}`
    } else {
      feedTrendEl.textContent = 'Not enough data'
    }
  }

  // Median Word Count
  setText('analytics-median-word-count', fmtWordCount(s.median_article_word_count))
  setText('analytics-median-word-count-trend', s.median_article_word_count_trend_label || 'Across all stored articles')
}

function populateCharts(data: AnalyticsOverview) {
  // Articles counts overview — stacked bar
  const articlesCountsEl = document.getElementById('articlesCountsChart')
  if (articlesCountsEl) {
    updateChart(articlesCountsEl, 'bar', data.articles_counts_overview as unknown as Record<string, unknown>, true)
  }

  // Feeds distribution — doughnut
  const feedsDistEl = document.getElementById('feedsDistributionChart')
  if (feedsDistEl) {
    updateChart(feedsDistEl, 'doughnut', data.feeds_distribution as unknown as Record<string, unknown>)
  }

  // RSS query traffic metric (sparkline in traffic metrics card)
  const rssMetricEl = document.getElementById('rssQueryMetricChart')
  if (rssMetricEl) {
    updateChart(rssMetricEl, 'line', data.traffic_metrics.rss_query as unknown as Record<string, unknown>)
  }

  // Article scrap traffic metric (sparkline in traffic metrics card)
  const scrapMetricEl = document.getElementById('articleScrapMetricChart')
  if (scrapMetricEl) {
    updateChart(scrapMetricEl, 'line', data.traffic_metrics.article_scrap as unknown as Record<string, unknown>)
  }

  // Article growth trends
  const growthEl = document.getElementById('articleGrowthChart')
  if (growthEl) {
    updateChart(growthEl, 'line', data.article_growth as unknown as Record<string, unknown>)
  }

  // Daily RSS query bar chart
  const dailyRssEl = document.getElementById('dailyRssQueryChart')
  if (dailyRssEl) {
    updateChart(dailyRssEl, 'bar', data.daily_rss_query as unknown as Record<string, unknown>)
  }

  // Update summary totals for traffic metrics card
  const rssTotal = (data.traffic_metrics.rss_query.datasets[0]?.data || []).reduce((a, b) => a + b, 0)
  const scrapSuccess = (data.traffic_metrics.article_scrap.datasets[0]?.data || []).reduce((a, b) => a + b, 0)
  const scrapFail = (data.traffic_metrics.article_scrap.datasets[1]?.data || []).reduce((a, b) => a + b, 0)
  setText('rssQueryTotal', fmtNumber(rssTotal))
  setText('articleScrapSuccessTotal', fmtNumber(scrapSuccess))
  setText('articleScrapFailTotal', fmtNumber(scrapFail))
}

function populateLatestArticles(data: AnalyticsOverview) {
  const tbody = document.getElementById('latestArticlesTableBody')
  if (!tbody) return

  if (data.latest_articles.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-muted text-center">No articles yet</td></tr>'
    return
  }

  tbody.innerHTML = data.latest_articles.map(a => `
    <tr>
      <td>${escapeHtml(a.feed_name)}</td>
      <td>${escapeHtml(a.article_title)}</td>
      <td>${fmtTime(a.update_time)}</td>
      <td>${fmtNumber(a.word_count)}</td>
      <td><a href="${escapeAttr(safeUrl(a.ori_url))}" target="_blank" rel="noopener" title="${escapeAttr(a.ori_url)}">${escapeHtml(truncateUrl(a.ori_url))}</a></td>
    </tr>
  `).join('')
}

function escapeHtml(s: string): string {
  const el = document.createElement('span')
  el.textContent = s
  return el.innerHTML
}

function escapeAttr(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function safeUrl(url: string): string {
  return /^https?:\/\//i.test(url) ? url : '#'
}
