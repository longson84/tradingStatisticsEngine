import { Fragment, useState } from "react"
import type { TradeRow } from "@/lib/api"
import { SectionTitle } from "./SectionTitle"

interface Props {
  trades: TradeRow[]
}

const CHECKPOINTS = [2, 5, 10] as const
type Checkpoint = (typeof CHECKPOINTS)[number]

const BUCKETS = [
  { label: "< -5%",    min: -Infinity, max: -5 },
  { label: "-5 to -2%", min: -5,     max: -2 },
  { label: "-2 to 0%",  min: -2,     max: 0  },
  { label: "0 to 2%",   min: 0,      max: 2  },
  { label: "2 to 5%",   min: 2,      max: 5  },
  { label: "> 5%",      min: 5,      max: Infinity },
]

// ── Scatter ───────────────────────────────────────────────────────────────────

const W = 480
const H = 280
const MX = { top: 20, right: 56, bottom: 48, left: 28 }
const IW = W - MX.left - MX.right
const IH = H - MX.top - MX.bottom

function niceTicks(min: number, max: number, n = 6): number[] {
  const range = max - min || 1
  const step = range / (n - 1)
  const magnitude = Math.pow(10, Math.floor(Math.log10(Math.abs(step) || 1)))
  const rounded = Math.ceil(step / magnitude) * magnitude
  const start = Math.floor(min / rounded) * rounded
  const ticks: number[] = []
  for (let v = start; v <= max + rounded * 0.01; v += rounded)
    ticks.push(Math.round(v * 10) / 10)
  return ticks
}

function fmt(n: number): string {
  return (n >= 0 ? "+" : "") + n.toFixed(2) + "%"
}

function signedLog(x: number): number {
  return Math.sign(x) * Math.log10(1 + Math.abs(x))
}

interface ScatterPoint {
  early: number
  final: number
  win: boolean
  entryDate: string
}

interface TooltipState {
  point: ScatterPoint
  clientX: number
  clientY: number
}

function EarlyScatter({ points, bar }: { points: ScatterPoint[]; bar: Checkpoint }) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const [logScale, setLogScale] = useState(false)

  if (points.length === 0) {
    return (
      <div>
        <p className="text-xs text-muted-foreground italic">No data for +{bar}d.</p>
      </div>
    )
  }

  const xs_vals = points.map(p => p.early)
  const rawYVals = points.map(p => p.final)

  const xPad = Math.abs(Math.min(...xs_vals)) * 0.08
  const yPad = Math.max(Math.abs(Math.min(...rawYVals)), Math.abs(Math.max(...rawYVals))) * 0.08

  const xMin = Math.min(...xs_vals) - xPad
  const xMax = Math.max(...xs_vals) + xPad
  const rawYMin = Math.min(...rawYVals) - yPad
  const rawYMax = Math.max(...rawYVals) + yPad

  const yTransform = logScale ? signedLog : (x: number) => x
  const yMin = yTransform(rawYMin)
  const yMax = yTransform(rawYMax)

  const xs = (v: number) => ((v - xMin) / (xMax - xMin)) * IW
  const ys = (v: number) => IH - ((yTransform(v) - yMin) / (yMax - yMin)) * IH

  const x0 = xs(0)
  const y0 = ys(0)

  const xTicks = niceTicks(xMin, xMax, 7)
  const yTicks = niceTicks(rawYMin, rawYMax, 7)

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const svgX = (e.clientX - rect.left) * (W / rect.width) - MX.left
    const svgY = (e.clientY - rect.top) * (H / rect.height) - MX.top
    let nearest: ScatterPoint | null = null
    let minDist = Infinity
    for (const p of points) {
      const d = Math.hypot(svgX - xs(p.early), svgY - ys(p.final))
      if (d < minDist) { minDist = d; nearest = p }
    }
    if (nearest && minDist < 18) {
      setTooltip({ point: nearest, clientX: e.clientX, clientY: e.clientY })
    } else {
      setTooltip(null)
    }
  }

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
          Min Return in First {bar}d vs Final Return
        </h3>
        <button
          onClick={() => setLogScale(s => !s)}
          className={`px-2 py-0.5 rounded border text-xs transition-colors ${
            logScale
              ? "border-blue-500 text-blue-400 bg-blue-500/10"
              : "border-border text-muted-foreground hover:bg-accent/40"
          }`}
        >
          Log Y
        </button>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full cursor-crosshair"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
      >
        <g transform={`translate(${MX.left},${MX.top})`}>
          {/* Grid lines */}
          {yTicks.map(v => (
            <line key={`gy${v}`} x1={0} y1={ys(v)} x2={IW} y2={ys(v)}
              stroke="#000" strokeOpacity={0.15} strokeWidth={1} />
          ))}
          {xTicks.map(v => (
            <line key={`gx${v}`} x1={xs(v)} y1={0} x2={xs(v)} y2={IH}
              stroke="#000" strokeOpacity={0.15} strokeWidth={1} />
          ))}

          {/* Zero crosshairs */}
          <line x1={x0} y1={0} x2={x0} y2={IH}
            stroke="hsl(var(--muted-foreground))" strokeDasharray="5,3" strokeWidth={1.2} />
          <line x1={0} y1={y0} x2={IW} y2={y0}
            stroke="hsl(var(--muted-foreground))" strokeDasharray="5,3" strokeWidth={1.2} />

          {/* Dots */}
          {points.map((p, i) => (
            <circle key={i}
              cx={xs(p.early)} cy={ys(p.final)} r={4}
              fill={p.win ? "#22c55e" : "#ef4444"}
              fillOpacity={0.65}
              stroke={p.win ? "#16a34a" : "#b91c1c"}
              strokeWidth={0.8}
            />
          ))}

          {/* Highlighted dot */}
          {tooltip && (
            <circle
              cx={xs(tooltip.point.early)} cy={ys(tooltip.point.final)} r={6}
              fill="none"
              stroke={tooltip.point.win ? "#4ade80" : "#f87171"}
              strokeWidth={2}
            />
          )}

          {/* Axes */}
          <line x1={0} y1={IH} x2={IW} y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />
          <line x1={0} y1={0} x2={0} y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />

          {/* X ticks & labels */}
          {xTicks.map(v => (
            <g key={`xt${v}`}>
              <line x1={xs(v)} y1={IH} x2={xs(v)} y2={IH + 5} stroke="hsl(var(--muted-foreground))" strokeWidth={1} />
              <text x={xs(v)} y={IH + 16} textAnchor="middle" fontSize={9} fill="hsl(var(--muted-foreground))">{v}%</text>
            </g>
          ))}
          <text x={IW / 2} y={IH + 36} textAnchor="middle" fontSize={10} fill="hsl(var(--foreground))" fontWeight="500">
            Min Return in First {bar}d
          </text>

          {/* Y ticks & labels — right side */}
          {yTicks.map(v => (
            <g key={`yt${v}`}>
              <line x1={IW} y1={ys(v)} x2={IW + 5} y2={ys(v)} stroke="hsl(var(--muted-foreground))" strokeWidth={1} />
              <text x={IW + 8} y={ys(v) + 3.5} textAnchor="start" fontSize={9} fill="hsl(var(--muted-foreground))">{v}%</text>
            </g>
          ))}
          <text
            textAnchor="middle" fontSize={10} fill="hsl(var(--foreground))" fontWeight="500"
            transform={`translate(${IW + 42}, ${IH / 2}) rotate(90)`}
          >
            Final Return
          </text>
        </g>
      </svg>

      {tooltip && (
        <div
          className="pointer-events-none fixed z-50 rounded border border-border bg-popover px-3 py-2 text-xs shadow-lg"
          style={{ left: tooltip.clientX + 14, top: tooltip.clientY - 40 }}
        >
          <div className={`font-semibold mb-1 ${tooltip.point.win ? "text-green-400" : "text-red-400"}`}>
            {tooltip.point.win ? "Winner" : "Loser"}
          </div>
          <div className="text-muted-foreground">
            Min {bar}d: <span className={`font-medium ${tooltip.point.early >= 0 ? "text-green-400" : "text-red-400"}`}>{fmt(tooltip.point.early)}</span>
          </div>
          <div className="text-muted-foreground">
            Final return: <span className={`font-medium ${tooltip.point.win ? "text-green-400" : "text-red-400"}`}>{fmt(tooltip.point.final)}</span>
          </div>
          <div className="mt-1 text-muted-foreground/60">{tooltip.point.entryDate}</div>
        </div>
      )}
    </div>
  )
}

// ── Win rate table ────────────────────────────────────────────────────────────

interface BucketStat {
  label: string
  checkpoints: Record<number, { count: number; wins: number; avgFinal: number } | null>
}

function winRateBadge(wr: number): React.ReactNode {
  return (
    <span className="tabular-nums text-foreground">
      {wr.toFixed(0)}%
    </span>
  )
}

function avgFinalBadge(avg: number): React.ReactNode {
  const [color, bg] = avg >= 0
    ? ["#15803d", "rgba(34,197,94,0.12)"]
    : ["#b91c1c", "rgba(239,68,68,0.12)"]
  return (
    <span
      className="inline-block px-1.5 py-0.5 rounded-sm text-[11px] font-bold tabular-nums"
      style={{ color, backgroundColor: bg }}
    >
      {fmt(avg)}
    </span>
  )
}

function WinRateTable({ bucketStats, totals, scatterPoints }: {
  bucketStats: BucketStat[]
  totals: Record<number, number>
  scatterPoints: Record<Checkpoint, ScatterPoint[]>
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-xs tabular-nums border-collapse [&_td]:border-r [&_td]:border-border [&_th]:border-r [&_th]:border-border">
        <thead>
          {/* Group header */}
          <tr className="bg-muted/40 border-b border-border text-[9px] uppercase tracking-widest text-muted-foreground/70">
            <th className="py-1.5 px-3 text-left font-semibold">Min Return</th>
            {CHECKPOINTS.map(bar => (
              <th key={bar} colSpan={6} className="py-1.5 px-3 text-left font-semibold border-l border-border">
                First {bar}d
              </th>
            ))}
          </tr>
          {/* Column header */}
          <tr className="bg-card border-b border-border text-muted-foreground uppercase tracking-wide">
            <th className="py-2 px-3 text-left font-medium w-28">#</th>
            {CHECKPOINTS.map(bar => (
              <Fragment key={bar}>
                <th className="py-2 px-3 text-right font-medium border-l border-border">Count</th>
                <th className="py-2 px-3 text-right font-medium">% Total</th>
                <th className="py-2 px-3 text-right font-medium text-green-500/80">Win</th>
                <th className="py-2 px-3 text-right font-medium text-red-500/80">Loss</th>
                <th className="py-2 px-3 text-right font-medium">Win Rate (%)</th>
                <th className="py-2 px-3 text-right font-medium">Avg Final</th>
              </Fragment>
            ))}
          </tr>
        </thead>
        <tbody>
          {bucketStats.map((row, ri) => (
            <tr
              key={ri}
              className={`border-b border-border hover:bg-blue-500/20 transition-colors ${ri % 2 === 1 ? "bg-card/40" : ""}`}
            >
              <td className="py-1.5 px-3 font-medium text-foreground" style={{ borderLeft: "3px solid transparent" }}>
                {row.label}
              </td>
              {CHECKPOINTS.map(bar => {
                const s = row.checkpoints[bar]
                const total = totals[bar] || 0
                if (!s || s.count === 0) {
                  return (
                    <Fragment key={bar}>
                      <td className="py-1.5 px-3 text-center text-muted-foreground/40 border-l border-border">—</td>
                      <td className="py-1.5 px-3 text-center text-muted-foreground/40">—</td>
                      <td className="py-1.5 px-3 text-center text-muted-foreground/40">—</td>
                      <td className="py-1.5 px-3 text-center text-muted-foreground/40">—</td>
                      <td className="py-1.5 px-3 text-center text-muted-foreground/40">—</td>
                      <td className="py-1.5 px-3 text-center text-muted-foreground/40">—</td>
                    </Fragment>
                  )
                }
                const losses = s.count - s.wins
                const pctTotal = total > 0 ? (s.count / total) * 100 : 0
                const wr = (s.wins / s.count) * 100
                return (
                  <Fragment key={bar}>
                    <td className="py-1.5 px-3 text-right text-foreground border-l border-border">{s.count}</td>
                    <td className="py-1.5 px-3 text-right text-muted-foreground">{pctTotal.toFixed(0)}%</td>
                    <td className="py-1.5 px-3 text-right text-green-400">{s.wins}</td>
                    <td className="py-1.5 px-3 text-right text-red-400">{losses}</td>
                    <td className="py-1.5 px-3 text-right">{winRateBadge(wr)}</td>
                    <td className="py-1.5 px-3 text-right">{avgFinalBadge(s.avgFinal)}</td>
                  </Fragment>
                )
              })}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-border bg-muted/40">
            <td className="py-1.5 px-3 text-[9px] uppercase tracking-widest text-muted-foreground/70 font-semibold">
              Total
            </td>
            {CHECKPOINTS.map(bar => {
              const pts = scatterPoints[bar]
              const total = totals[bar]
              if (total === 0) {
                return (
                  <Fragment key={bar}>
                    <td className="py-1.5 px-3 text-center text-muted-foreground/40 border-l border-border" colSpan={6}>—</td>
                  </Fragment>
                )
              }
              const totalWins = pts.filter(p => p.win).length
              const totalLosses = total - totalWins
              return (
                <Fragment key={bar}>
                  <td className="py-1.5 px-3 text-right font-semibold text-foreground border-l border-border">{total}</td>
                  <td className="py-1.5 px-3 text-right text-muted-foreground">100%</td>
                  <td className="py-1.5 px-3 text-right text-green-400 font-semibold">{totalWins}</td>
                  <td className="py-1.5 px-3 text-right text-red-400 font-semibold">{totalLosses}</td>
                  <td className="py-1.5 px-3 text-center text-muted-foreground/40">—</td>
                  <td className="py-1.5 px-3 text-center text-muted-foreground/40">—</td>
                </Fragment>
              )
            })}
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────

export function EarlyTradeBehavior({ trades }: Props) {
  const closed = trades.filter(
    t => t.exit_date != null && t.return_pct != null && t.early_returns && Object.keys(t.early_returns).length > 0
  )

  if (closed.length === 0) return null

  // Build scatter points per checkpoint
  const scatterPoints: Record<Checkpoint, ScatterPoint[]> = {
    2: [], 5: [], 10: [],
  }
  for (const t of closed) {
    for (const bar of CHECKPOINTS) {
      const early = t.early_returns[String(bar)]
      if (early != null && t.return_pct != null) {
        scatterPoints[bar].push({
          early,
          final: t.return_pct,
          win: t.return_pct > 0,
          entryDate: t.entry_date,
        })
      }
    }
  }

  // Build win rate table
  const bucketStats: BucketStat[] = BUCKETS.map(b => {
    const checkpoints: BucketStat["checkpoints"] = {}
    for (const bar of CHECKPOINTS) {
      const inBucket = scatterPoints[bar].filter(p => p.early >= b.min && p.early < b.max)
      if (inBucket.length === 0) {
        checkpoints[bar] = null
      } else {
        const wins = inBucket.filter(p => p.win).length
        const avgFinal = inBucket.reduce((s, p) => s + p.final, 0) / inBucket.length
        checkpoints[bar] = { count: inBucket.length, wins, avgFinal }
      }
    }
    return { label: b.label, checkpoints }
  })

  return (
    <div>
      <SectionTitle>Early Trade Behavior</SectionTitle>
      <p className="text-xs text-muted-foreground mb-4">
        For each closed trade, shows the <strong>lowest</strong> return within the first 2, 5, and 10 bars from entry — only while the position is still open.
        Reveals whether early adverse moves predict the final outcome.
      </p>

      <WinRateTable
        bucketStats={bucketStats}
        totals={{ 2: scatterPoints[2].length, 5: scatterPoints[5].length, 10: scatterPoints[10].length }}
        scatterPoints={scatterPoints}
      />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3 mt-6">
        {CHECKPOINTS.map(bar => (
          <EarlyScatter key={bar} points={scatterPoints[bar]} bar={bar} />
        ))}
      </div>

      <div className="mt-2 flex gap-4 text-xs text-muted-foreground px-1">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-green-500 opacity-70" />Winners
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-red-500 opacity-70" />Losers
        </span>
        <span className="ml-auto text-muted-foreground/50">x = lowest close in first N bars; trades closed before window excluded</span>
      </div>
    </div>
  )
}
