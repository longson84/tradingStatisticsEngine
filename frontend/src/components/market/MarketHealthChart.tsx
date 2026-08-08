import {
  ColorType,
  createChart,
  LineSeries,
  LineStyle,
  type LineData,
  type Time,
} from "lightweight-charts"
import { useEffect, useRef } from "react"
import type { MarketHealthMarket } from "@/lib/api"


interface Props {
  market: MarketHealthMarket
}

const MARKET_COLORS: Record<MarketHealthMarket["universe"], string> = {
  US500: "#16a34a",
  US2000: "#7c3aed",
  US100: "#2563eb",
  VNALL: "#0f766e",
  VN100: "#dc2626",
  VN30: "#ea580c",
  VNMID: "#d97706",
  VNSML: "#db2777",
}


export function MarketHealthChart({ market }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || market.series.length === 0) return

    const isDark = document.documentElement.classList.contains("dark")
    const chart = createChart(ref.current, {
      width: ref.current.clientWidth,
      height: 320,
      layout: {
        background: {
          type: ColorType.Solid,
          color: isDark ? "#262626" : "#ffffff",
        },
        textColor: isDark ? "#a1a1aa" : "#6b7280",
        fontFamily: "inherit",
      },
      grid: {
        vertLines: { color: isDark ? "#3f3f46" : "#e5e7eb" },
        horzLines: { color: isDark ? "#3f3f46" : "#e5e7eb" },
      },
      rightPriceScale: {
        borderColor: isDark ? "#52525b" : "#d4d4d8",
        scaleMargins: { top: 0.08, bottom: 0.08 },
      },
      timeScale: {
        borderColor: isDark ? "#52525b" : "#d4d4d8",
      },
    })

    const healthSeries = chart.addSeries(LineSeries, {
      color: MARKET_COLORS[market.universe],
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    })
    const healthData: LineData<Time>[] = market.series.map(point => ({
      time: point.date as Time,
      value: point.median_distance,
    }))
    healthSeries.setData(healthData)

    const runningMedian10YSeries = chart.addSeries(LineSeries, {
      color: isDark ? "#d4d4d8" : "#52525b",
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: true,
    })
    const runningMedian10YData: LineData<Time>[] = market.series.map(point => ({
      time: point.date as Time,
      value: point.running_median_10y,
    }))
    runningMedian10YSeries.setData(runningMedian10YData)

    const runningMedian5YSeries = chart.addSeries(LineSeries, {
      color: "#06b6d4",
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: true,
    })
    const runningMedian5YData: LineData<Time>[] = market.series.map(point => ({
      time: point.date as Time,
      value: point.running_median_5y,
    }))
    runningMedian5YSeries.setData(runningMedian5YData)

    const runningMedian1YSeries = chart.addSeries(LineSeries, {
      color: "#f59e0b",
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: true,
    })
    const runningMedian1YData: LineData<Time>[] = market.series.map(point => ({
      time: point.date as Time,
      value: point.running_median_1y,
    }))
    runningMedian1YSeries.setData(runningMedian1YData)

    chart.timeScale().fitContent()
    const observer = new ResizeObserver(entries => {
      const width = entries[0]?.contentRect.width
      if (width && width > 0) chart.applyOptions({ width })
    })
    observer.observe(ref.current)

    return () => {
      observer.disconnect()
      chart.remove()
    }
  }, [market])

  return (
    <section className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="flex flex-wrap items-center gap-5 border-b border-border px-4 py-3 text-xs">
        <span className="font-semibold">{market.universe}</span>
        <span className="inline-flex items-center gap-1.5 text-muted-foreground">
          <span
            className="h-0.5 w-5"
            style={{ backgroundColor: MARKET_COLORS[market.universe] }}
          />
          Median distance
        </span>
        <span className="inline-flex items-center gap-1.5 text-muted-foreground">
          <span className="w-5 border-t-2 border-dashed border-foreground/70" />
          Running median 10Y
        </span>
        <span className="inline-flex items-center gap-1.5 text-muted-foreground">
          <span className="w-5 border-t-2 border-dashed border-cyan-500" />
          Running median 5Y
        </span>
        <span className="inline-flex items-center gap-1.5 text-muted-foreground">
          <span className="w-5 border-t-2 border-dashed border-amber-500" />
          Running median 1Y
        </span>
      </div>
      <div ref={ref} />
    </section>
  )
}
