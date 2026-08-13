import { useEffect, useRef, useState } from "react"
import {
  ColorType,
  createChart,
  CrosshairMode,
  LineSeries,
  LineStyle,
  type LineData,
  type Time,
} from "lightweight-charts"

import type { UniverseStatsResult } from "@/lib/api"


const UNIVERSE_STATS_SERIES_COLORS = [
  "#2563eb",
  "#dc2626",
  "#16a34a",
  "#9333ea",
  "#ea580c",
  "#0891b2",
  "#ca8a04",
  "#db2777",
  "#4f46e5",
  "#0f766e",
]

interface PaneLegendValue {
  universeCode: string
  color: string
  value: number
}

interface CursorLegend {
  date: string
  high: PaneLegendValue[]
  low: PaneLegendValue[]
}


export function UniverseStatsChart({ results }: { results: UniverseStatsResult[] }) {
  const ref = useRef<HTMLDivElement>(null)
  const resultsKey = results.map(result => `${result.universe_code}:${result.last_date}`).join("|")
  const [cursorLegend, setCursorLegend] = useState<{
    resultsKey: string
    legend: CursorLegend
  } | null>(null)
  const legend = cursorLegend?.resultsKey === resultsKey
    ? cursorLegend.legend
    : latestLegend(results)

  useEffect(() => {
    const container = ref.current
    if (!container || results.length === 0) return
    const isDark = document.documentElement.classList.contains("dark")
    const zeroLineColor = isDark ? "#71717a" : "#94a3b8"
    const chart = createChart(container, {
      width: container.clientWidth,
      height: 720,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: isDark ? "#a1a1aa" : "#6b7280",
        fontFamily: "inherit",
      },
      grid: {
        vertLines: { color: isDark ? "#27272a" : "#f1f5f9" },
        horzLines: { color: isDark ? "#27272a" : "#f1f5f9" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: isDark ? "#a1a1aa" : "#64748b" },
        horzLine: { color: isDark ? "#71717a" : "#94a3b8" },
      },
      rightPriceScale: {
        borderColor: isDark ? "#3f3f46" : "#e2e8f0",
        scaleMargins: { top: 0.16, bottom: 0.12 },
      },
      timeScale: { borderColor: isDark ? "#3f3f46" : "#e2e8f0" },
      localization: { priceFormatter: (value: number) => `${value.toFixed(1)}%` },
    })

    const seriesPairs = results.map((result, index) => {
      const color = UNIVERSE_STATS_SERIES_COLORS[index % UNIVERSE_STATS_SERIES_COLORS.length]
      const highSeries = chart.addSeries(LineSeries, {
        title: result.universe_code,
        color,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
      }, 0)
      highSeries.setData(result.points.map(point => ({
        time: point.date as LineData["time"],
        value: point.median_distance_from_high,
      })))

      const lowSeries = chart.addSeries(LineSeries, {
        title: result.universe_code,
        color,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
      }, 1)
      lowSeries.setData(result.points.map(point => ({
        time: point.date as LineData["time"],
        value: point.median_distance_from_low,
      })))

      if (index === 0) {
        for (const series of [highSeries, lowSeries]) {
          series.createPriceLine({
            price: 0,
            color: zeroLineColor,
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: false,
            title: "",
          })
        }
      }
      return { result, color, highSeries, lowSeries }
    })

    const handleCrosshairMove: Parameters<typeof chart.subscribeCrosshairMove>[0] = param => {
      if (param.time == null || param.point == null) {
        setCursorLegend(null)
        return
      }
      const high: PaneLegendValue[] = []
      const low: PaneLegendValue[] = []
      for (const pair of seriesPairs) {
        const highValue = lineValue(param.seriesData.get(pair.highSeries))
        const lowValue = lineValue(param.seriesData.get(pair.lowSeries))
        if (highValue != null) {
          high.push({
            universeCode: pair.result.universe_code,
            color: pair.color,
            value: highValue,
          })
        }
        if (lowValue != null) {
          low.push({
            universeCode: pair.result.universe_code,
            color: pair.color,
            value: lowValue,
          })
        }
      }
      setCursorLegend({
        resultsKey,
        legend: { date: formatChartTime(param.time), high, low },
      })
    }
    chart.subscribeCrosshairMove(handleCrosshairMove)

    const panes = chart.panes()
    panes[0]?.setStretchFactor(1)
    panes[1]?.setStretchFactor(1)
    chart.timeScale().fitContent()

    const observer = new ResizeObserver(entries => {
      const width = entries[0]?.contentRect.width
      if (width && width > 0) chart.applyOptions({ width })
    })
    observer.observe(container)
    return () => {
      observer.disconnect()
      chart.unsubscribeCrosshairMove(handleCrosshairMove)
      chart.remove()
    }
  }, [results, resultsKey])

  return (
    <div className="relative">
      <div className="pointer-events-none absolute left-3 top-3 z-10 rounded bg-card/85 px-2 py-1 backdrop-blur-sm">
        <div className="text-xs font-semibold">Median distance from High 200</div>
        <PaneLegend date={legend.date} values={legend.high} />
      </div>
      <div className="pointer-events-none absolute left-3 top-[calc(50%+0.25rem)] z-10 rounded bg-card/85 px-2 py-1 backdrop-blur-sm">
        <div className="text-xs font-semibold">Median distance from Low 200</div>
        <PaneLegend date={legend.date} values={legend.low} />
      </div>
      <div ref={ref} className="w-full" />
    </div>
  )
}


function PaneLegend({ date, values }: { date: string; values: PaneLegendValue[] }) {
  return (
    <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[10px]">
      <span className="tabular-nums text-muted-foreground">{date}</span>
      {values.map(item => (
        <span key={item.universeCode} className="flex items-center gap-1 tabular-nums">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: item.color }} />
          <span className="text-muted-foreground">{item.universeCode}</span>
          <span className="font-semibold text-foreground">{item.value.toFixed(1)}%</span>
        </span>
      ))}
    </div>
  )
}


function latestLegend(results: UniverseStatsResult[]): CursorLegend {
  const latestDate = results.reduce(
    (latest, result) => result.last_date > latest ? result.last_date : latest,
    "",
  )
  return {
    date: latestDate,
    high: latestPaneValues(results, "median_distance_from_high"),
    low: latestPaneValues(results, "median_distance_from_low"),
  }
}


function latestPaneValues(
  results: UniverseStatsResult[],
  metric: "median_distance_from_high" | "median_distance_from_low",
): PaneLegendValue[] {
  return results.map((result, index) => ({
    universeCode: result.universe_code,
    color: UNIVERSE_STATS_SERIES_COLORS[index % UNIVERSE_STATS_SERIES_COLORS.length],
    value: result.points[result.points.length - 1][metric],
  }))
}


function lineValue(data: unknown): number | null {
  if (data && typeof data === "object" && "value" in data) {
    const value = data.value
    return typeof value === "number" ? value : null
  }
  return null
}


function formatChartTime(time: Time): string {
  if (typeof time === "string") return time
  if (typeof time === "number") return new Date(time * 1000).toISOString().slice(0, 10)
  return [time.year, time.month, time.day]
    .map((value, index) => index === 0 ? String(value) : String(value).padStart(2, "0"))
    .join("-")
}
