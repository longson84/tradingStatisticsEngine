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
  markets: MarketHealthMarket[]
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


export function MarketHealthChart({ markets }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || markets.length === 0) return

    const isDark = document.documentElement.classList.contains("dark")
    const chart = createChart(ref.current, {
      width: ref.current.clientWidth,
      height: 440,
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

    for (const market of markets) {
      const series = chart.addSeries(LineSeries, {
        title: market.universe,
        color: MARKET_COLORS[market.universe],
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
      })
      const data: LineData<Time>[] = market.series.map(point => ({
        time: point.date as Time,
        value: point.median_distance,
      }))
      series.setData(data)
    }

    const allPoints = markets.flatMap(market => market.series)
    if (allPoints.length > 0) {
      const first = allPoints.reduce(
        (earliest, point) => point.date < earliest ? point.date : earliest,
        allPoints[0].date,
      )
      const last = allPoints.reduce(
        (latest, point) => point.date > latest ? point.date : latest,
        allPoints[0].date,
      )
      const thresholds = [-40, -30, -20, -10]
      for (const threshold of thresholds) {
        chart.addSeries(LineSeries, {
          color: "rgba(107,114,128,0.35)",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: false,
        }).setData([
          { time: first as Time, value: threshold },
          { time: last as Time, value: threshold },
        ])
      }
    }

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
  }, [markets])

  return (
    <section className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="flex flex-wrap items-center gap-5 border-b border-border px-4 py-3 text-xs">
        <span className="font-semibold">
          Median distance from 200-session high
        </span>
        {markets.map(market => (
          <span key={market.universe} className="inline-flex items-center gap-1.5 text-muted-foreground">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: MARKET_COLORS[market.universe] }}
            />
            {market.universe}
          </span>
        ))}
      </div>
      <div ref={ref} />
    </section>
  )
}
