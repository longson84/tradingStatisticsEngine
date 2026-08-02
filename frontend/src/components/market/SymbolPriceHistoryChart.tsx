import {
  CandlestickSeries,
  ColorType,
  createChart,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  type LineStyleOptions,
  type MouseEventParams,
  type SeriesOptionsCommon,
  type Time,
} from "lightweight-charts"
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import type { SymbolPricePoint } from "@/lib/api"
import {
  exponentialMovingAverage,
  simpleMovingAverage,
} from "@/lib/moving-averages"


const SMA_COLORS = ["#f59e0b", "#e11d48", "#8b5cf6", "#06b6d4", "#84cc16"]
const EMA_COLORS = ["#ec4899", "#14b8a6", "#f97316", "#6366f1", "#22c55e"]
const RELATIVE_STRENGTH_COLOR = "#2563eb"
type ChartInterval = "daily" | "weekly" | "monthly"
const CHART_INTERVALS: ChartInterval[] = ["daily", "weekly", "monthly"]

export interface PriceHistoryCursorSnapshot {
  date: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  change: number | null
  changePct: number | null
  volume: number | null
  volumeMa20: number | null
  trailingPe: number | null
  trailingPb: number | null
  epsTtm: number | null
  sharesOutstanding: number | null
  relativeStrength: number | null
  indicators: Array<{ label: string; value: number | null }>
}


export function SymbolPriceHistoryChart({
  symbol,
  relativeStrengthBenchmark,
  prices,
  smaLengths,
  emaLengths,
  onCursorSnapshotChange,
}: {
  symbol: string
  relativeStrengthBenchmark: "VN30" | "SPX"
  prices: SymbolPricePoint[]
  smaLengths: number[]
  emaLengths: number[]
  onCursorSnapshotChange: (snapshot: PriceHistoryCursorSnapshot | null) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const labelsRef = useRef<HTMLDivElement>(null)
  const axesRef = useRef<HTMLDivElement>(null)
  const [interval, setInterval] = useState<ChartInterval>("daily")
  const [paneSnapshot, setPaneSnapshot] = useState<PriceHistoryCursorSnapshot | null>(null)
  const chartPrices = useMemo(
    () => resamplePrices(prices, interval),
    [interval, prices],
  )

  useEffect(() => {
    const container = containerRef.current
    if (!container || chartPrices.length < 2) return

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 1220,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#6b7280",
        fontFamily: "inherit",
      },
      grid: {
        vertLines: { color: "rgba(107, 114, 128, 0.14)" },
        horzLines: { color: "rgba(107, 114, 128, 0.14)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "#6b7280" },
        horzLine: { color: "#6b7280", visible: true, labelVisible: true },
      },
      rightPriceScale: { borderColor: "#374151" },
      timeScale: {
        borderColor: "#374151",
        timeVisible: false,
        rightOffset: 4,
      },
    })
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#16a34a",
      downColor: "#dc2626",
      wickUpColor: "#16a34a",
      wickDownColor: "#dc2626",
      borderUpColor: "#16a34a",
      borderDownColor: "#dc2626",
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
      priceLineVisible: true,
      lastValueVisible: true,
      title: "",
    })
    series.setData(chartPrices.map(point => ({
      time: point.date as Time,
      open: point.open,
      high: point.high,
      low: point.low,
      close: point.close,
    })))

    const closeValues = chartPrices.map(point => ({ date: point.date, value: point.close }))
    const priceIndexByDate = new Map(chartPrices.map((point, index) => [point.date, index]))
    const smaSeries = addMovingAverages(chart, "SMA", smaLengths, closeValues, SMA_COLORS)
    const emaSeries = addMovingAverages(chart, "EMA", emaLengths, closeValues, EMA_COLORS)
    const relativeStrengthSeries = chart.addSeries(LineSeries, {
      title: "",
      color: RELATIVE_STRENGTH_COLOR,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    }, 1)
    relativeStrengthSeries.setData(chartPrices.flatMap(point => (
      point.relative_strength == null
        ? []
        : [{ time: point.date as Time, value: point.relative_strength }]
    )))

    const volumeSeries = chart.addSeries(HistogramSeries, {
      title: "",
      priceFormat: {
        type: "custom",
        minMove: 1,
        formatter: formatCompactQuantity,
      },
      priceLineVisible: false,
      lastValueVisible: true,
    }, 2)
    volumeSeries.setData(chartPrices.flatMap(point => (
      point.volume == null
        ? []
        : [{
            time: point.date as Time,
            value: point.volume,
            color: point.close >= point.open ? "rgba(34, 197, 94, 0.55)" : "rgba(239, 68, 68, 0.55)",
          }]
    )))

    const volumeMa = chart.addSeries(LineSeries, {
      title: "",
      color: "#f59e0b",
      lineWidth: 2,
      priceFormat: {
        type: "custom",
        minMove: 1,
        formatter: formatCompactQuantity,
      },
      priceLineVisible: false,
      lastValueVisible: true,
    }, 2)
    volumeMa.setData(simpleMovingAverage(
      chartPrices.map(point => ({ date: point.date, value: point.volume })),
      20,
    ).map(point => ({ time: point.date as Time, value: point.value })))

    const trailingPeSeries = chart.addSeries(LineSeries, {
      title: "",
      color: "#8b5cf6",
      lineWidth: 2,
      priceFormat: {
        type: "custom",
        formatter: (value: number) => value.toFixed(2),
      },
      priceLineVisible: false,
      lastValueVisible: true,
    }, 3)
    trailingPeSeries.setData(chartPrices.flatMap(point => (
      point.trailing_pe == null
        ? []
        : [{ time: point.date as Time, value: point.trailing_pe }]
    )))

    const trailingPbSeries = chart.addSeries(LineSeries, {
      title: "",
      color: "#0891b2",
      lineWidth: 2,
      priceFormat: {
        type: "custom",
        formatter: (value: number) => value.toFixed(2),
      },
      priceLineVisible: false,
      lastValueVisible: true,
    }, 4)
    trailingPbSeries.setData(chartPrices.flatMap(point => (
      point.trailing_pb == null
        ? []
        : [{ time: point.date as Time, value: point.trailing_pb }]
    )))

    const epsSeries = chart.addSeries(LineSeries, {
      title: "",
      color: "#db2777",
      lineWidth: 2,
      priceFormat: {
        type: "custom",
        formatter: (value: number) => value.toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }),
      },
      priceLineVisible: false,
      lastValueVisible: true,
    }, 5)
    epsSeries.setData(chartPrices.flatMap(point => (
      point.eps_ttm == null
        ? []
        : [{ time: point.date as Time, value: point.eps_ttm }]
    )))

    const sharesSeries = chart.addSeries(HistogramSeries, {
      title: "",
      color: "rgba(14, 165, 233, 0.65)",
      priceFormat: {
        type: "custom",
        minMove: 1,
        formatter: formatCompactQuantity,
      },
      priceLineVisible: false,
      lastValueVisible: true,
    }, 6)
    sharesSeries.setData(chartPrices.flatMap(point => (
      point.shares_outstanding == null
        ? []
        : [{
            time: point.date as Time,
            value: point.shares_outstanding,
            color: "rgba(14, 165, 233, 0.65)",
          }]
    )))

    let lastSnapshotDate: string | null = null
    const handleCrosshairMove = (param: MouseEventParams<Time>) => {
      if (param.time == null || param.point == null) {
        return
      }
      const snapshotDate = formatCrosshairDate(param.time)
      const priceIndex = priceIndexByDate.get(snapshotDate)
      const currentClose = crosshairSeriesValue(param.seriesData.get(series), "close")
      const previousClose = priceIndex != null && priceIndex > 0
        ? chartPrices[priceIndex - 1].close
        : null
      const change = currentClose != null && previousClose != null
        ? currentClose - previousClose
        : null
      const nextSnapshot: PriceHistoryCursorSnapshot = {
        date: snapshotDate,
        open: crosshairSeriesValue(param.seriesData.get(series), "open"),
        high: crosshairSeriesValue(param.seriesData.get(series), "high"),
        low: crosshairSeriesValue(param.seriesData.get(series), "low"),
        close: currentClose,
        change,
        changePct: change != null && previousClose != null && previousClose !== 0
          ? (change / previousClose) * 100
          : null,
        volume: crosshairSeriesValue(param.seriesData.get(volumeSeries), "value"),
        volumeMa20: crosshairSeriesValue(param.seriesData.get(volumeMa), "value"),
        trailingPe: crosshairSeriesValue(param.seriesData.get(trailingPeSeries), "value"),
        trailingPb: crosshairSeriesValue(param.seriesData.get(trailingPbSeries), "value"),
        epsTtm: crosshairSeriesValue(param.seriesData.get(epsSeries), "value"),
        sharesOutstanding: crosshairSeriesValue(
          param.seriesData.get(sharesSeries),
          "value",
        ),
        relativeStrength: crosshairSeriesValue(
          param.seriesData.get(relativeStrengthSeries),
          "value",
        ),
        indicators: [...smaSeries, ...emaSeries].map(indicator => ({
          label: indicator.label,
          value: crosshairSeriesValue(param.seriesData.get(indicator.series), "value"),
        })),
      }
      if (lastSnapshotDate !== nextSnapshot.date) {
        lastSnapshotDate = nextSnapshot.date
        setPaneSnapshot(nextSnapshot)
        onCursorSnapshotChange(nextSnapshot)
      }
    }
    chart.subscribeCrosshairMove(handleCrosshairMove)

    chart.panes()[0]?.setStretchFactor(4)
    chart.panes()[1]?.setStretchFactor(1)
    chart.panes()[2]?.setStretchFactor(1)
    chart.panes()[3]?.setStretchFactor(1)
    chart.panes()[4]?.setStretchFactor(1)
    chart.panes()[5]?.setStretchFactor(1)
    chart.panes()[6]?.setStretchFactor(1)
    chart.priceScale("right", 0).applyOptions({
      scaleMargins: { top: 0.05, bottom: 0.12 },
    })
    chart.priceScale("right", 1).applyOptions({
      scaleMargins: { top: 0.15, bottom: 0.18 },
    })
    chart.priceScale("right", 2).applyOptions({
      scaleMargins: { top: 0.15, bottom: 0.18 },
    })
    chart.priceScale("right", 3).applyOptions({
      scaleMargins: { top: 0.15, bottom: 0.18 },
    })
    chart.priceScale("right", 4).applyOptions({
      scaleMargins: { top: 0.15, bottom: 0.18 },
    })
    chart.priceScale("right", 5).applyOptions({
      scaleMargins: { top: 0.15, bottom: 0.18 },
    })
    chart.priceScale("right", 6).applyOptions({
      scaleMargins: { top: 0.15, bottom: 0 },
    })
    chart.timeScale().fitContent()

    const alignPaneLabels = () => {
      const labels = labelsRef.current?.children
      if (!labels) return
      let paneTop = 0
      chart.panes().forEach((pane, index) => {
        const label = labels.item(index) as HTMLElement | null
        if (label) label.style.top = `${paneTop + 8}px`
        paneTop += pane.getHeight()
      })
    }

    const alignPaneTimeAxes = () => {
      const axes = axesRef.current?.children
      if (!axes) return
      const panes = chart.panes()
      const plotWidth = chart.paneSize(0).width
      const tickCount = Math.max(2, Math.min(6, Math.floor(plotWidth / 150)))
      let paneTop = 0
      for (let paneIndex = 0; paneIndex < panes.length - 1; paneIndex += 1) {
        const paneHeight = panes[paneIndex].getHeight()
        const axis = axes.item(paneIndex) as HTMLElement | null
        if (axis) {
          axis.style.top = `${paneTop + paneHeight - 22}px`
          axis.style.width = `${plotWidth}px`
          Array.from(axis.children).forEach((child, tickIndex) => {
            const tick = child as HTMLElement
            if (tickIndex >= tickCount) {
              tick.style.display = "none"
              return
            }
            const x = 55 + ((plotWidth - 110) * tickIndex / (tickCount - 1))
            const time = chart.timeScale().coordinateToTime(x)
            tick.style.display = "block"
            tick.style.left = `${x}px`
            tick.textContent = formatPaneAxisDate(time, interval)
          })
        }
        paneTop += paneHeight
      }
    }

    const alignOverlays = () => {
      alignPaneLabels()
      alignPaneTimeAxes()
    }
    alignOverlays()
    chart.timeScale().subscribeVisibleLogicalRangeChange(alignPaneTimeAxes)

    const observer = new ResizeObserver(entries => {
      const width = entries[0]?.contentRect.width
      if (width) {
        chart.applyOptions({ width })
        alignOverlays()
      }
    })
    observer.observe(container)
    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove)
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(alignPaneTimeAxes)
      observer.disconnect()
      chart.remove()
    }
  }, [chartPrices, emaLengths, interval, onCursorSnapshotChange, relativeStrengthBenchmark, smaLengths, symbol])

  return (
    <div>
      <div className="mb-3 flex items-center gap-3">
        <div className="flex overflow-hidden rounded border border-border text-xs">
          {CHART_INTERVALS.map(value => (
            <button
              key={value}
              type="button"
              onClick={() => {
                setPaneSnapshot(null)
                onCursorSnapshotChange(null)
                setInterval(value)
              }}
              aria-pressed={interval === value}
              className={`px-3 py-1.5 capitalize transition-colors ${
                interval === value
                  ? "bg-accent font-medium text-foreground"
                  : "text-muted-foreground hover:bg-accent/40"
              }`}
            >
              {value}
            </button>
          ))}
        </div>
      </div>
      <div className="relative">
        <div
          ref={containerRef}
          className="w-full"
          aria-label={`${symbol} ${interval} price history chart`}
        />
        <div ref={labelsRef} className="pointer-events-none absolute inset-0 z-10">
          <PaneLabel>
            <OhlcLegendRow snapshot={paneSnapshot} />
            {smaLengths.map((length, index) => {
              const label = `SMA ${length}`
              return (
                <PaneValueRow
                  key={label}
                  label={label}
                  value={indicatorSnapshotValue(paneSnapshot, label)}
                  color={SMA_COLORS[index % SMA_COLORS.length]}
                />
              )
            })}
            {emaLengths.map((length, index) => {
              const label = `EMA ${length}`
              return (
                <PaneValueRow
                  key={label}
                  label={label}
                  value={indicatorSnapshotValue(paneSnapshot, label)}
                  color={EMA_COLORS[index % EMA_COLORS.length]}
                />
              )
            })}
          </PaneLabel>
          <PaneLabel>
            <PaneValueRow
              label={`Relative strength vs ${relativeStrengthBenchmark}`}
              value={paneSnapshot?.relativeStrength ?? null}
              color={RELATIVE_STRENGTH_COLOR}
            />
          </PaneLabel>
          <PaneLabel>
            <PaneValueRow label="Volume" value={paneSnapshot?.volume ?? null} decimals={0} />
            <PaneValueRow
              label="Volume MA20"
              value={paneSnapshot?.volumeMa20 ?? null}
              color="#f59e0b"
              decimals={0}
            />
          </PaneLabel>
          <PaneLabel>
            <PaneValueRow label="Trailing P/E" value={paneSnapshot?.trailingPe ?? null} color="#8b5cf6" />
          </PaneLabel>
          <PaneLabel>
            <PaneValueRow label="Price / Book" value={paneSnapshot?.trailingPb ?? null} color="#0891b2" />
          </PaneLabel>
          <PaneLabel>
            <PaneValueRow label="EPS TTM" value={paneSnapshot?.epsTtm ?? null} color="#db2777" />
          </PaneLabel>
          <PaneLabel>
            <PaneValueRow
              label="Outstanding shares"
              value={paneSnapshot?.sharesOutstanding ?? null}
              color="#0ea5e9"
              decimals={0}
            />
          </PaneLabel>
        </div>
        <div ref={axesRef} className="pointer-events-none absolute inset-0 z-10">
          {Array.from({ length: 6 }, (_, paneIndex) => (
            <div
              key={paneIndex}
              className="absolute left-0 h-[22px] border-t border-border/70 bg-background/80 text-[10px] text-muted-foreground backdrop-blur-sm"
            >
              {Array.from({ length: 6 }, (_, tickIndex) => (
                <span
                  key={tickIndex}
                  className="absolute top-1 -translate-x-1/2 whitespace-nowrap tabular-nums"
                />
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}


function crosshairSeriesValue(
  data: unknown,
  field: "open" | "high" | "low" | "close" | "value",
): number | null {
  if (data == null || typeof data !== "object" || !(field in data)) return null
  const value = (data as Record<string, unknown>)[field]
  return typeof value === "number" && Number.isFinite(value) ? value : null
}


function formatCrosshairDate(time: Time): string {
  if (typeof time === "number") return new Date(time * 1000).toISOString().slice(0, 10)
  if (typeof time === "string") return time
  return `${time.year}-${String(time.month).padStart(2, "0")}-${String(time.day).padStart(2, "0")}`
}


function PaneLabel({ children }: { children: ReactNode }) {
  return (
    <div className="absolute left-2 space-y-0.5 rounded bg-background/85 px-2 py-1 text-[11px] font-normal shadow-sm backdrop-blur-sm">
      {children}
    </div>
  )
}


function formatPaneAxisDate(time: Time | null, interval: ChartInterval): string {
  if (time == null) return ""
  if (typeof time === "number") {
    return formatAxisDate(new Date(time * 1000), interval)
  }
  const value = typeof time === "string"
    ? time
    : `${time.year}-${String(time.month).padStart(2, "0")}-${String(time.day).padStart(2, "0")}`
  const date = new Date(`${value}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return value
  return formatAxisDate(date, interval)
}


function formatAxisDate(date: Date, interval: ChartInterval): string {
  if (interval === "monthly") {
    return date.toLocaleDateString(undefined, { year: "numeric", month: "short" })
  }
  return date.toLocaleDateString(undefined, {
    year: "2-digit",
    month: "short",
    day: "2-digit",
  })
}


function formatCompactQuantity(value: number): string {
  const absolute = Math.abs(value)
  if (absolute >= 1_000_000_000) return `${formatScaled(value / 1_000_000_000)}B`
  if (absolute >= 1_000_000) return `${formatScaled(value / 1_000_000)}M`
  if (absolute >= 1_000) return `${formatScaled(value / 1_000)}K`
  return formatScaled(value)
}


function formatScaled(value: number): string {
  const decimals = Math.abs(value) >= 100 ? 0 : Math.abs(value) >= 10 ? 1 : 2
  return value.toFixed(decimals).replace(/\.0+$|(?<=\.[0-9])0+$/, "")
}


function OhlcLegendRow({ snapshot }: { snapshot: PriceHistoryCursorSnapshot | null }) {
  const changeColor = snapshot?.change == null
    ? "text-muted-foreground"
    : snapshot.change >= 0 ? "text-emerald-600" : "text-red-600"
  return (
    <div className="flex flex-wrap items-center gap-x-3 whitespace-nowrap tabular-nums">
      <span>O {formatPaneValue(snapshot?.open ?? null)}</span>
      <span>H {formatPaneValue(snapshot?.high ?? null)}</span>
      <span>L {formatPaneValue(snapshot?.low ?? null)}</span>
      <span>C {formatPaneValue(snapshot?.close ?? null)}</span>
      <span className={changeColor}>
        Chg {formatSignedPaneValue(snapshot?.change ?? null)}
        {" "}({formatSignedPaneValue(snapshot?.changePct ?? null)}%)
      </span>
    </div>
  )
}


function PaneValueRow({
  label,
  value,
  color = "#6b7280",
  decimals = 2,
}: {
  label: string
  value: number | null
  color?: string
  decimals?: number
}) {
  return (
    <div className="flex items-center gap-1.5 whitespace-nowrap tabular-nums">
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
      <span>{label}</span>
      <span>{formatPaneValue(value, decimals)}</span>
    </div>
  )
}


function indicatorSnapshotValue(
  snapshot: PriceHistoryCursorSnapshot | null,
  label: string,
): number | null {
  return snapshot?.indicators.find(indicator => indicator.label === label)?.value ?? null
}


function formatPaneValue(value: number | null, decimals = 2): string {
  if (value == null) return "—"
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}


function formatSignedPaneValue(value: number | null): string {
  if (value == null) return "—"
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`
}


function resamplePrices(
  prices: SymbolPricePoint[],
  interval: ChartInterval,
): SymbolPricePoint[] {
  if (interval === "daily") return prices

  const groups = new Map<string, SymbolPricePoint>()
  for (const point of prices) {
    const key = interval === "weekly" ? isoWeekKey(point.date) : point.date.slice(0, 7)
    const existing = groups.get(key)
    if (!existing) {
      groups.set(key, { ...point })
      continue
    }
    groups.set(key, {
      ...point,
      open: existing.open,
      high: Math.max(existing.high, point.high),
      low: Math.min(existing.low, point.low),
      volume: addVolumes(existing.volume, point.volume),
    })
  }
  return Array.from(groups.values())
}


function isoWeekKey(value: string): string {
  const [year, month, day] = value.split("-").map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  const weekday = date.getUTCDay() || 7
  date.setUTCDate(date.getUTCDate() - weekday + 1)
  return date.toISOString().slice(0, 10)
}


function addVolumes(left: number | null, right: number | null): number | null {
  if (left == null && right == null) return null
  return (left ?? 0) + (right ?? 0)
}


function addMovingAverages(
  chart: ReturnType<typeof createChart>,
  kind: "SMA" | "EMA",
  lengths: number[],
  values: Array<{ date: string; value: number }>,
  colors: string[],
) {
  return lengths.map((length, index) => {
    const options: Partial<LineStyleOptions & SeriesOptionsCommon> = {
      title: "",
      color: colors[index % colors.length],
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    }
    const movingAverage = chart.addSeries(LineSeries, options)
    const points = kind === "SMA"
      ? simpleMovingAverage(values, length)
      : exponentialMovingAverage(values, length)
    movingAverage.setData(points.map(point => ({
      time: point.date as Time,
      value: point.value,
    })))
    return { label: `${kind} ${length}`, series: movingAverage }
  })
}
