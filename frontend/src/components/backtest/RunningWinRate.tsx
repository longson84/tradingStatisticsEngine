import { useMemo, useState } from "react"
import type { TradeRow } from "@/lib/api"
import { fmtDate, fmtPct } from "@/lib/format"

interface Props {
  trades: TradeRow[]
}

interface WinRatePoint {
  date: string
  tradeNumber: number
  wins: number
  losses: number
  winRate: number
  returnPct: number
}

interface TooltipState {
  point: WinRatePoint
  clientX: number
  clientY: number
}

const W = 520
const H = 240
const MX = { top: 20, right: 28, bottom: 44, left: 52 }
const IW = W - MX.left - MX.right
const IH = H - MX.top - MX.bottom

function computeRunningWinRate(trades: TradeRow[]): WinRatePoint[] {
  const closed = trades
    .filter(t => t.exit_date != null && t.return_pct != null)
    .sort((a, b) => {
      const dateOrder = a.exit_date!.localeCompare(b.exit_date!)
      if (dateOrder !== 0) return dateOrder
      return a.entry_date.localeCompare(b.entry_date)
    })

  let wins = 0
  return closed.map((trade, index) => {
    const returnPct = trade.return_pct!
    if (returnPct > 0) wins += 1
    const tradeNumber = index + 1

    return {
      date: trade.exit_date!,
      tradeNumber,
      wins,
      losses: tradeNumber - wins,
      winRate: (wins / tradeNumber) * 100,
      returnPct,
    }
  })
}

function makePath(points: WinRatePoint[], xs: (d: string) => number, ys: (v: number) => number) {
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"}${xs(point.date).toFixed(1)},${ys(point.winRate).toFixed(1)}`)
    .join(" ")
}

function fmtSigned(n: number) {
  return `${n >= 0 ? "+" : ""}${fmtPct(n)}`
}

export function RunningWinRate({ trades }: Props) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const points = useMemo(() => computeRunningWinRate(trades), [trades])

  if (points.length === 0) {
    return (
      <div>
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mt-1 mb-3">
          Running Win Rate
        </h2>
        <p className="text-sm text-muted-foreground italic">No closed trades.</p>
      </div>
    )
  }

  const firstMs = Date.parse(points[0].date)
  const lastMs = Date.parse(points.at(-1)!.date)
  const dateRange = lastMs - firstMs || 1
  const xs = (date: string) => ((Date.parse(date) - firstMs) / dateRange) * IW
  const ys = (value: number) => IH - (value / 100) * IH

  const ticks = [0, 25, 50, 75, 100]
  const yearLabels: Array<{ year: string; x: number }> = []
  let lastYear = ""
  for (const point of points) {
    const year = point.date.slice(0, 4)
    if (year !== lastYear) {
      yearLabels.push({ year, x: xs(point.date) })
      lastYear = year
    }
  }

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const svgX = (e.clientX - rect.left) * (W / rect.width) - MX.left
    const svgY = (e.clientY - rect.top) * (H / rect.height) - MX.top

    let nearest: WinRatePoint | null = null
    let minDist = Infinity
    for (const point of points) {
      const dist = Math.hypot(svgX - xs(point.date), svgY - ys(point.winRate))
      if (dist < minDist) {
        minDist = dist
        nearest = point
      }
    }

    if (nearest && minDist < 24) {
      setTooltip({ point: nearest, clientX: e.clientX, clientY: e.clientY })
    } else {
      setTooltip(null)
    }
  }

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mt-1">
          Running Win Rate
        </h2>
        <div className="text-xs text-muted-foreground">
          {fmtPct(points.at(-1)!.winRate, 1)} after {points.length} trades
        </div>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full cursor-default"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
      >
        <defs>
          <linearGradient id="winRateFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="rgba(16,185,129,0.22)" />
            <stop offset="100%" stopColor="rgba(16,185,129,0.02)" />
          </linearGradient>
        </defs>
        <g transform={`translate(${MX.left},${MX.top})`}>
          {ticks.map(tick => (
            <line
              key={tick}
              x1={0}
              y1={ys(tick)}
              x2={IW}
              y2={ys(tick)}
              stroke="#000"
              strokeOpacity={tick === 50 ? 0.18 : 0.1}
              strokeWidth={tick === 50 ? 1.4 : 1}
            />
          ))}

          <path
            d={`${makePath(points, xs, ys)} L${xs(points.at(-1)!.date).toFixed(1)},${IH} L${xs(points[0].date).toFixed(1)},${IH} Z`}
            fill="url(#winRateFill)"
          />
          <path
            d={makePath(points, xs, ys)}
            fill="none"
            stroke="#10b981"
            strokeWidth={2}
          />

          {points.map(point => (
            <circle
              key={`${point.date}-${point.tradeNumber}`}
              cx={xs(point.date)}
              cy={ys(point.winRate)}
              r={point.returnPct > 0 ? 2.7 : 2.3}
              fill={point.returnPct > 0 ? "#10b981" : "#ef4444"}
              stroke="hsl(var(--background))"
              strokeWidth={1}
            />
          ))}

          <line x1={0} y1={ys(50)} x2={IW} y2={ys(50)}
            stroke="hsl(var(--muted-foreground))" strokeDasharray="4,3" strokeWidth={1} />
          <line x1={0} y1={IH} x2={IW} y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />
          <line x1={0} y1={0} x2={0} y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />

          {yearLabels.map(({ year, x }) => (
            <g key={year}>
              <line x1={x} y1={IH} x2={x} y2={IH + 4}
                stroke="hsl(var(--muted-foreground))" strokeWidth={1} />
              <text x={x} y={IH + 15} textAnchor="middle" fontSize={9}
                fill="hsl(var(--muted-foreground))">{year}</text>
            </g>
          ))}

          {ticks.map(tick => (
            <g key={tick}>
              <line x1={0} y1={ys(tick)} x2={-4} y2={ys(tick)}
                stroke="hsl(var(--muted-foreground))" strokeWidth={1} />
              <text x={-8} y={ys(tick) + 3.5} textAnchor="end" fontSize={9}
                fill="hsl(var(--muted-foreground))">{tick}%</text>
            </g>
          ))}
          <text x={-(IH / 2)} y={-38} textAnchor="middle" fontSize={10}
            fill="hsl(var(--foreground))" fontWeight="500" transform="rotate(-90)">
            Win Rate %
          </text>
        </g>
      </svg>

      {tooltip && (
        <div
          className="pointer-events-none fixed z-50 rounded border border-border bg-popover px-3 py-2 text-xs shadow-lg"
          style={{ left: tooltip.clientX + 14, top: tooltip.clientY - 78 }}
        >
          <div className="font-semibold text-foreground mb-1">
            Trade #{tooltip.point.tradeNumber} - {fmtDate(tooltip.point.date)}
          </div>
          <div className="text-muted-foreground">
            Win rate: <span className="font-medium text-emerald-400">{fmtPct(tooltip.point.winRate, 1)}</span>
          </div>
          <div className="text-muted-foreground">
            Wins / Losses: <span className="font-medium text-foreground">{tooltip.point.wins} / {tooltip.point.losses}</span>
          </div>
          <div className="text-muted-foreground">
            Trade return: <span className={tooltip.point.returnPct > 0 ? "font-medium text-emerald-400" : "font-medium text-red-400"}>
              {fmtSigned(tooltip.point.returnPct)}
            </span>
          </div>
        </div>
      )}

      <div className="mt-1.5 flex gap-4 text-xs text-muted-foreground px-1">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-4 h-0.5 bg-emerald-500" />Cumulative win rate
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-red-500" />Losing close
        </span>
        <span className="ml-auto text-muted-foreground/50">based on closed trades by exit date</span>
      </div>
    </div>
  )
}
