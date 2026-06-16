/* global getComputedStyle, ResizeObserver */
import * as echarts from 'echarts/core'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent
} from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'

echarts.use([
  LineChart, BarChart, PieChart,
  GridComponent, TooltipComponent, LegendComponent, TitleComponent,
  SVGRenderer
])

type ChartType = 'line' | 'bar' | 'pie' | 'doughnut'

const tokens = () => {
  const cs = getComputedStyle(document.documentElement)
  return {
    primary: cs.getPropertyValue('--primary').trim() || '#1ABB9C',
    primaryDk: cs.getPropertyValue('--primary-dk').trim() || '#149a80',
    primaryLt: cs.getPropertyValue('--primary-lt').trim() || '#4fd1bb',
    text: cs.getPropertyValue('--text').trim() || '#1e2633',
    textSecondary: cs.getPropertyValue('--text-secondary').trim() || '#626d7d'
  }
}

function buildOption(type: ChartType, data: Record<string, unknown>, t: ReturnType<typeof tokens>, stacked = false): echarts.EChartsCoreOption {
  const base: echarts.EChartsCoreOption = {
    textStyle: { color: t.text, fontFamily: 'Inter, system-ui, sans-serif' },
    tooltip: { trigger: type === 'pie' || type === 'doughnut' ? 'item' : 'axis' }
  }

  switch (type) {
    case 'line':
      return {
        ...base,
        xAxis: { type: 'category', data: data.labels as string[], axisLabel: { color: t.textSecondary } },
        yAxis: { type: 'value', axisLabel: { color: t.textSecondary }, splitLine: { lineStyle: { color: t.textSecondary, opacity: 0.2 } } },
        series: (data.datasets as Array<{ label: string; data: number[]; color?: string }>).map((ds, i) => ({
          name: ds.label,
          type: 'line' as const,
          data: ds.data,
          smooth: true,
          itemStyle: { color: ds.color || (i === 0 ? t.primary : t.primaryLt) },
          areaStyle: { opacity: 0.1 }
        })),
        legend: { textStyle: { color: t.textSecondary } }
      }

    case 'bar':
      return {
        ...base,
        xAxis: { type: 'category', data: data.labels as string[], axisLabel: { color: t.textSecondary } },
        yAxis: { type: 'value', axisLabel: { color: t.textSecondary }, splitLine: { lineStyle: { color: t.textSecondary, opacity: 0.2 } } },
        series: (data.datasets as Array<{ label: string; data: number[]; color?: string }>).map((ds, i) => ({
          name: ds.label,
          type: 'bar' as const,
          data: ds.data,
          stack: stacked ? 'total' : undefined,
          itemStyle: { color: ds.color || (i === 0 ? t.primary : t.primaryLt), borderRadius: stacked ? [0, 0, 0, 0] : [4, 4, 0, 0] }
        })),
        legend: { textStyle: { color: t.textSecondary } }
      }

    case 'pie':
    case 'doughnut':
      return {
        ...base,
        series: [{
          type: 'pie' as const,
          radius: type === 'doughnut' ? ['50%', '70%'] : '70%',
          data: (data.items as Array<{ name: string; value: number; color?: string }>).map((item, i) => ({
            name: item.name,
            value: item.value,
            itemStyle: { color: item.color || [t.primary, t.primaryLt, t.primaryDk, '#e8e8e8', '#999'][i % 5] }
          })),
          label: { color: t.text }
        }],
        legend: { orient: 'horizontal' as const, bottom: 0, textStyle: { color: t.textSecondary } }
      }

    default:
      return base
  }
}

export function initCharts() {
  document.querySelectorAll<HTMLElement>('.chart:not([data-inited])').forEach((el) => {
    el.dataset.inited = 'true'
    const type = (el.dataset.chartType || 'line') as ChartType
    const stacked = el.dataset.chartStacked === 'true'
    let data: Record<string, unknown> = {}
    try {
      data = JSON.parse(el.dataset.chartData || '{}')
    } catch { /* empty */ }

    const chart = echarts.init(el, undefined, { renderer: 'svg' })
    chart.setOption(buildOption(type, data, tokens(), stacked))
    new ResizeObserver(() => chart.resize()).observe(el)
  })
}

/**
 * Update a chart element with new data at runtime.
 * If the chart isn't initialized yet, it will be initialized first.
 */
export function updateChart(el: HTMLElement, type: ChartType, data: Record<string, unknown>, stacked = false) {
  // Update the data attribute for theme refresh compatibility
  el.dataset.chartData = JSON.stringify(data)
  el.dataset.chartType = type
  if (stacked) el.dataset.chartStacked = 'true'

  let inst = echarts.getInstanceByDom(el)
  if (!inst) {
    el.dataset.inited = 'true'
    inst = echarts.init(el, undefined, { renderer: 'svg' })
    new ResizeObserver(() => inst!.resize()).observe(el)
  }
  inst.setOption(buildOption(type, data, tokens(), stacked), { notMerge: true })
}

export function refreshChartsTheme() {
  const t = tokens()
  document.querySelectorAll<HTMLElement>('.chart[data-inited]').forEach((el) => {
    const inst = echarts.getInstanceByDom(el)
    if (!inst) return
    const type = (el.dataset.chartType || 'line') as ChartType
    const stacked = el.dataset.chartStacked === 'true'
    let data: Record<string, unknown> = {}
    try {
      data = JSON.parse(el.dataset.chartData || '{}')
    } catch { /* empty */ }
    inst.setOption(buildOption(type, data, t, stacked), { notMerge: true })
  })
}

document.addEventListener('theme-changed', () => refreshChartsTheme())
