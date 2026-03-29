import {
  createChart,
  ColorType,
  LineStyle,
  LineSeries,
  createSeriesMarkers,
} from "lightweight-charts"
import { useEffect, useRef } from "react"
import type { TimeSeriesPoint, ZoneStat, ZoneEntry } from "@/lib/api"

interface Props {
  timeSeries: TimeSeriesPoint[]
  zoneStats: ZoneStat[]
  entries: ZoneEntry[]
}

const ZONE_COLORS: Record<number, string> = {
  5:  "#dc2626",
  10: "#ea580c",
  15: "#d97706",
  20: "#ca8a04",
  25: "#65a30d",
  30: "#16a34a",
}
function zoneColor(pct: number) { return ZONE_COLORS[pct] ?? "#9ca3af" }

// Match the backtest EquityChart theme exactly
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
  crosshair: {
    vertLine: { color: "#6b7280" },
    horzLine: { color: "#6b7280" },
  },
  rightPriceScale: { borderColor: "#374151" },
  timeScale: { borderColor: "#374151" },
} as const

export function PriceFactorChart({ timeSeries, zoneStats, entries }: Props) {
  const priceRef  = useRef<HTMLDivElement>(null)
  const factorRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!priceRef.current || !factorRef.current || timeSeries.length < 2) return

    const priceData  = timeSeries.map(p => ({ time: p.date as any, value: p.price }))
    const factorData = timeSeries.map(p => ({ time: p.date as any, value: p.factor }))
    const first = priceData[0].time
    const last  = priceData[priceData.length - 1].time

    // Lookup maps for the crosshair tooltip
    const factorByTime = new Map<string, number>(
      timeSeries.map(p => [p.date, p.factor])
    )
    const priceByTime = new Map<string, number>(
      timeSeries.map(p => [p.date, p.price])
    )

    // Percentile of each factor value vs the full series distribution
    const sortedFactors = [...timeSeries.map(p => p.factor)].sort((a, b) => a - b)
    function pctOf(val: number): number {
      let lo = 0, hi = sortedFactors.length
      while (lo < hi) { const m = (lo + hi) >> 1; if (sortedFactors[m] < val) lo = m + 1; else hi = m }
      return (lo / sortedFactors.length) * 100
    }
    const percentileByTime = new Map<string, number>(
      timeSeries.map(p => [p.date, pctOf(p.factor)])
    )

    // ── Price chart (top pane) ────────────────────────────────────────────────
    const priceChart = createChart(priceRef.current, {
      ...BASE_OPTS,
      height: 260,
      timeScale: { ...BASE_OPTS.timeScale, visible: false },
    })
    const priceSeries = priceChart.addSeries(LineSeries, {
      color: "#3b82f6",
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: true,
    })
    priceSeries.setData(priceData)

    // ── Factor chart (bottom pane) ────────────────────────────────────────────
    const factorChart = createChart(factorRef.current, {
      ...BASE_OPTS,
      height: 160,
    })
    const factorSeries = factorChart.addSeries(LineSeries, {
      color: "#f59e0b",
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: true,
    })
    factorSeries.setData(factorData)

    // Zero line
    factorChart.addSeries(LineSeries, {
      color: "rgba(107,114,128,0.4)",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
    }).setData([{ time: first, value: 0 }, { time: last, value: 0 }])

    // Zone threshold lines — more prominent so bands are clearly readable
    zoneStats.slice(0, 6).forEach(z => {
      const s = factorChart.addSeries(LineSeries, {
        color: zoneColor(z.zone_pct) + "bb",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: true,
        title: `P${z.zone_pct}`,
      })
      s.setData([
        { time: first, value: z.threshold_value },
        { time: last,  value: z.threshold_value },
      ])
    })

    // ── Zone entry circles ON THE PRICE CHART ────────────────────────────────
    // Show ALL zone crossings (not just level=0) so progressive deepening is
    // visible: P30 → P25 → P20 each get their own circle as the factor descends.
    const priceMarkers = entries
      .filter(e => e.zone_pct <= 30)
      .map(e => ({
        time: e.start_date as any,
        position: "belowBar" as const,
        color: zoneColor(e.zone_pct),
        shape: "circle" as const,
        size: e.is_active ? 2 : 1,
      }))
      .sort((a, b) => (a.time < b.time ? -1 : 1))
    createSeriesMarkers(priceSeries, priceMarkers)

    // ── Crosshair tooltip ────────────────────────────────────────────────────
    priceRef.current.style.position = "relative"

    const tooltip = document.createElement("div")
    Object.assign(tooltip.style, {
      position:       "absolute",
      display:        "none",
      pointerEvents:  "none",
      zIndex:         "20",
      background:     "rgba(10,14,26,0.88)",
      border:         "1px solid rgba(255,255,255,0.10)",
      borderRadius:   "6px",
      padding:        "8px 12px",
      fontSize:       "11px",
      lineHeight:     "1.7",
      color:          "#e2e8f0",
      backdropFilter: "blur(6px)",
      minWidth:       "158px",
      whiteSpace:     "nowrap",
    })
    priceRef.current.appendChild(tooltip)

    function renderTooltip(
      timeStr: string,
      priceVal: number | undefined,
      factorVal: number | undefined,
      pctVal: number | undefined,
      pointX: number,
      containerWidth: number,
    ) {
      if (priceVal == null) { tooltip.style.display = "none"; return }
      const pctColor = pctVal != null && pctVal <= 10 ? "#f97316"
                     : pctVal != null && pctVal <= 25 ? "#eab308"
                     : "#9ca3af"
      tooltip.innerHTML =
        `<div style="color:#6b7280;font-size:10px;margin-bottom:3px">${timeStr}</div>` +
        `<div><span style="color:#6b7280">Price &nbsp;&nbsp;</span><span style="color:#93c5fd;font-weight:600">${priceVal.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span></div>` +
        `<div><span style="color:#6b7280">Factor &nbsp;</span><span style="color:#fbbf24;font-weight:600">${factorVal != null ? factorVal.toFixed(4) : "—"}</span></div>` +
        `<div><span style="color:#6b7280">Pct &nbsp;&nbsp;&nbsp;&nbsp;</span><span style="color:${pctColor};font-weight:600">${pctVal != null ? pctVal.toFixed(1) + "%" : "—"}</span></div>`

      const tw = 168
      const left = pointX + 16 + tw > containerWidth ? pointX - tw - 8 : pointX + 16
      tooltip.style.left    = left + "px"
      tooltip.style.top     = "8px"
      tooltip.style.display = "block"
    }

    priceChart.subscribeCrosshairMove(params => {
      if (!params.time || !params.point) { tooltip.style.display = "none"; return }
      const entry = params.seriesData.get(priceSeries) as { value: number } | undefined
      const timeStr = String(params.time)
      renderTooltip(
        timeStr,
        entry?.value ?? priceByTime.get(timeStr),
        factorByTime.get(timeStr),
        percentileByTime.get(timeStr),
        params.point.x,
        priceRef.current!.clientWidth,
      )
    })

    factorChart.subscribeCrosshairMove(params => {
      if (!params.time || !params.point) { tooltip.style.display = "none"; return }
      const timeStr = String(params.time)
      renderTooltip(
        timeStr,
        priceByTime.get(timeStr),
        factorByTime.get(timeStr),
        percentileByTime.get(timeStr),
        params.point.x,
        priceRef.current!.clientWidth,
      )
    })

    // ── Sync time scales ──────────────────────────────────────────────────────
    let syncing = false
    priceChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
      if (syncing || !range) return
      syncing = true
      factorChart.timeScale().setVisibleLogicalRange(range)
      syncing = false
    })
    factorChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
      if (syncing || !range) return
      syncing = true
      priceChart.timeScale().setVisibleLogicalRange(range)
      syncing = false
    })

    priceChart.timeScale().fitContent()
    factorChart.timeScale().fitContent()

    return () => {
      tooltip.remove()
      priceChart.remove()
      factorChart.remove()
    }
  }, [timeSeries, zoneStats, entries])

  if (!timeSeries.length) return null

  return (
    <div className="rounded-lg border border-border overflow-hidden bg-card">
      {/* Legend */}
      <div className="flex items-center gap-4 px-4 py-2 border-b border-border text-[10px] text-muted-foreground flex-wrap">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-0.5 rounded bg-blue-500 inline-block" /> Price
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-0.5 rounded bg-amber-400 inline-block" /> Factor
        </span>
        <span className="text-muted-foreground/30">|</span>
        {[5, 10, 15, 20, 25, 30].map(p => (
          <span key={p} className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: zoneColor(p) }} />
            <span style={{ color: zoneColor(p) }} className="font-semibold">P{p}</span>
          </span>
        ))}
        <span className="ml-auto text-muted-foreground/30 italic text-[9px]">scroll / pinch to zoom</span>
      </div>
      <div ref={priceRef} />
      <div className="border-t border-border/40" />
      <div ref={factorRef} />
    </div>
  )
}
