import { useEffect, useRef, useState } from "react"
import {
  createChart,
  LineSeries,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type HistogramData,
  ColorType,
} from "lightweight-charts"

type Interval = "daily" | "weekly" | "monthly"

interface Props {
  strategyLabel: string
  equityStrategy: Record<string, number>
  equityBah: Record<string, number>
}

// ── Data helpers ─────────────────────────────────────────────────────────────

function toLineSeries(curve: Record<string, number>): LineData[] {
  return Object.entries(curve)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([time, value]) => ({ time: time as LineData["time"], value }))
}

function resample(data: LineData[], interval: Interval): LineData[] {
  if (interval === "daily") return data
  const groups = new Map<string, LineData>()
  for (const point of data) {
    const [y, m, d] = (point.time as string).split("-").map(Number)
    let key: string
    if (interval === "weekly") {
      const date = new Date(y, m - 1, d)
      const dow = date.getDay() || 7
      date.setDate(date.getDate() - dow + 1) // Monday
      key = date.toISOString().slice(0, 10)
    } else {
      key = `${y}-${String(m).padStart(2, "0")}`
    }
    groups.set(key, point) // last bar in period wins
  }
  return Array.from(groups.values())
}

function toDrawdown(data: LineData[]): HistogramData[] {
  let peak = -Infinity
  return data.map(({ time, value }) => {
    if (value > peak) peak = value
    const dd = peak > 0 ? ((value / peak) - 1) * 100 : 0
    return { time, value: dd, color: dd < -10 ? "#ef4444" : "#f97316" }
  })
}

const fmtNav = (p: number) =>
  p.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })

const fmtDd = (p: number) =>
  p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%"

// ── Chart options ─────────────────────────────────────────────────────────────

const BASE_OPTS = {
  layout: {
    background: { type: ColorType.Solid, color: "transparent" },
    textColor: "#6b7280",
    fontFamily: "inherit",
  },
  grid: {
    vertLines: { color: "#1f2937" },
    horzLines: { color: "#1f2937" },
  },
  crosshair: { vertLine: { color: "#6b7280" }, horzLine: { color: "#6b7280" } },
  rightPriceScale: { borderColor: "#374151" },
  timeScale: { borderColor: "#374151" },
} as const

// ── Component ─────────────────────────────────────────────────────────────────

export function EquityChart({ strategyLabel, equityStrategy, equityBah }: Props) {
  const [logScale, setLogScale] = useState(false)
  const [interval, setInterval] = useState<Interval>("daily")

  const equityRef = useRef<HTMLDivElement>(null)
  const ddRef = useRef<HTMLDivElement>(null)
  const chartEq = useRef<IChartApi | null>(null)
  const chartDd = useRef<IChartApi | null>(null)
  const stratSeries = useRef<ISeriesApi<"Line"> | null>(null)
  const bahSeries = useRef<ISeriesApi<"Line"> | null>(null)
  const ddSeries = useRef<ISeriesApi<"Histogram"> | null>(null)

  // ── Build charts once ────────────────────────────────────────────────────
  useEffect(() => {
    if (!equityRef.current || !ddRef.current) return

    chartEq.current = createChart(equityRef.current, {
      ...BASE_OPTS,
      height: 280,
      timeScale: { ...BASE_OPTS.timeScale, visible: false },
    })

    stratSeries.current = chartEq.current.addSeries(LineSeries, {
      color: "#3b82f6",
      lineWidth: 2,
      title: strategyLabel,
      priceLineVisible: false,
      priceFormat: { type: "custom", formatter: fmtNav },
    })

    bahSeries.current = chartEq.current.addSeries(LineSeries, {
      color: "#6b7280",
      lineWidth: 1,
      lineStyle: 2,
      title: "Buy & Hold",
      priceLineVisible: false,
      priceFormat: { type: "custom", formatter: fmtNav },
    })

    chartDd.current = createChart(ddRef.current, {
      ...BASE_OPTS,
      height: 110,
    })

    ddSeries.current = chartDd.current.addSeries(HistogramSeries, {
      color: "#f97316",
      priceLineVisible: false,
      priceFormat: { type: "custom", formatter: fmtDd },
    })

    // sync time scales
    chartEq.current.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (range) chartDd.current?.timeScale().setVisibleLogicalRange(range)
    })
    chartDd.current.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (range) chartEq.current?.timeScale().setVisibleLogicalRange(range)
    })

    const ro = new ResizeObserver(() => {
      const w = equityRef.current?.clientWidth
      if (w) {
        chartEq.current?.applyOptions({ width: w })
        chartDd.current?.applyOptions({ width: w })
      }
    })
    ro.observe(equityRef.current)

    return () => {
      ro.disconnect()
      chartEq.current?.remove()
      chartDd.current?.remove()
    }
  }, [equityStrategy, equityBah, strategyLabel])

  // ── Update data when interval changes ────────────────────────────────────
  useEffect(() => {
    if (!stratSeries.current || !bahSeries.current || !ddSeries.current) return
    const stratData = resample(toLineSeries(equityStrategy), interval)
    const bahData = resample(toLineSeries(equityBah), interval)
    stratSeries.current.setData(stratData)
    bahSeries.current.setData(bahData)
    ddSeries.current.setData(toDrawdown(stratData))
    chartEq.current?.timeScale().fitContent()
    chartDd.current?.timeScale().fitContent()
  }, [interval, equityStrategy, equityBah])

  // ── Update log scale without rebuilding ──────────────────────────────────
  useEffect(() => {
    chartEq.current?.priceScale("right").applyOptions({ mode: logScale ? 1 : 0 })
  }, [logScale])

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mt-1">Equity Curve</h2>
        <div className="flex items-center gap-2">
          {/* Interval selector */}
          <div className="flex rounded border border-border overflow-hidden text-xs">
            {(["daily", "weekly", "monthly"] as Interval[]).map((iv) => (
              <button
                key={iv}
                onClick={() => setInterval(iv)}
                className={`px-2.5 py-1 capitalize transition-colors ${
                  interval === iv
                    ? "bg-accent text-foreground"
                    : "text-muted-foreground hover:bg-accent/40"
                }`}
              >
                {iv[0].toUpperCase() + iv.slice(1)}
              </button>
            ))}
          </div>
          {/* Log scale toggle */}
          <button
            onClick={() => setLogScale(s => !s)}
            className={`px-2.5 py-1 rounded border text-xs transition-colors ${
              logScale
                ? "border-blue-500 text-blue-400 bg-blue-500/10"
                : "border-border text-muted-foreground hover:bg-accent/40"
            }`}
          >
            Log
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-border overflow-hidden bg-background">
        <div ref={equityRef} className="w-full" />
        <div className="border-t border-border/40" />
        <div ref={ddRef} className="w-full" />
      </div>

      <div className="mt-1.5 flex gap-4 text-xs text-muted-foreground px-1">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-4 h-0.5 bg-blue-500" />{strategyLabel}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-4 h-0.5 bg-gray-500" />Buy &amp; Hold
        </span>
        <span className="ml-auto">
          Drawdown: <span className="text-orange-400">orange</span> / <span className="text-red-400">&gt;10% red</span>
        </span>
      </div>
    </div>
  )
}
