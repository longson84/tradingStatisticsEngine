import { useMemo, useState } from "react"
import { SectionTitle } from "./SectionTitle"

interface Props {
  equityStrategy: Record<string, number>
  label?: string
}

interface DDPeriod {
  startDate: string
  troughDate: string
  recoveryDate: string | null
  depthPct: number       // negative, e.g. -15.3
  daysToTrough: number
  recoveryDays: number | null
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function calDays(d1: string, d2: string) {
  return Math.round((Date.parse(d2) - Date.parse(d1)) / 86_400_000)
}

function computeAllPeriods(curve: Record<string, number>): DDPeriod[] {
  const sorted = Object.entries(curve).sort(([a], [b]) => a.localeCompare(b))
  if (sorted.length < 2) return []

  const periods: DDPeriod[] = []
  let peak = sorted[0][1]
  let inDD = false
  let startDate = ""
  let startPeak = peak
  let troughVal = Infinity
  let troughDate = ""

  for (const [date, val] of sorted) {
    if (val >= peak) {
      if (inDD) {
        const depth = (troughVal / startPeak - 1) * 100
        if (depth < -5)
          periods.push({
            startDate, troughDate, recoveryDate: date, depthPct: depth,
            daysToTrough: calDays(startDate, troughDate), recoveryDays: calDays(troughDate, date),
          })
        inDD = false
      }
      peak = val
    } else {
      if (!inDD) { inDD = true; startDate = date; startPeak = peak; troughVal = val; troughDate = date }
      else if (val < troughVal) { troughVal = val; troughDate = date }
    }
  }
  if (inDD) {
    const depth = (troughVal / startPeak - 1) * 100
    if (depth < -5)
      periods.push({
        startDate, troughDate, recoveryDate: null, depthPct: depth,
        daysToTrough: calDays(startDate, troughDate), recoveryDays: null,
      })
  }
  return periods
}

function pctile(arr: number[], p: number): number {
  if (!arr.length) return 0
  const s = [...arr].sort((a, b) => a - b)
  const i = (p / 100) * (s.length - 1)
  const lo = Math.floor(i), hi = Math.ceil(i)
  return s[lo] + (s[hi] - s[lo]) * (i - lo)
}

// ── Depth Distribution Table ──────────────────────────────────────────────────

const DEPTH_PCTS = [50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 98]
const SATURATE_AT = 30

function heatCell(val: number): React.CSSProperties {
  const intensity = Math.min(val / SATURATE_AT, 1)
  return {
    color: intensity > 0.4 ? "#b91c1c" : "#dc2626",
    backgroundColor: `rgba(239, 68, 68, ${0.08 + intensity * 0.38})`,
  }
}

function DepthDistributionTable({ periods }: { periods: DDPeriod[] }) {
  const depths = periods.map(p => Math.abs(p.depthPct))
  const n = depths.length

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs tabular-nums border-collapse">
          <thead>
            <tr className="border-b border-border text-muted-foreground uppercase tracking-wide">
              <th className="py-2 px-3 text-left font-medium">Depth (%)</th>
              <th className="py-2 px-3 text-right font-medium">Value</th>
              <th className="py-2 px-3 text-right font-medium">Count</th>
            </tr>
          </thead>
          <tbody>
            {DEPTH_PCTS.map(p => {
              const val = pctile(depths, p)
              const count = Math.round((p / 100) * n)
              const isMedian = p === 50
              return (
                <tr
                  key={p}
                  className={`border-b border-border/40 ${isMedian ? "border-t border-border/60" : ""}`}
                >
                  <td className={`py-1.5 px-3 ${isMedian ? "font-semibold text-foreground" : "text-muted-foreground"}`}>
                    P{p}
                    {isMedian && (
                      <span className="ml-1.5 text-[9px] text-muted-foreground/60 font-normal uppercase tracking-wider">
                        median
                      </span>
                    )}
                  </td>
                  <td
                    className={`py-1.5 px-3 text-right ${isMedian ? "font-bold" : "font-medium"}`}
                    style={heatCell(val)}
                  >
                    -{val.toFixed(1)}%
                  </td>
                  <td className={`py-1.5 px-3 text-right ${isMedian ? "font-semibold text-foreground" : "text-foreground"}`}>
                    {count}
                  </td>
                </tr>
              )
            })}
            <tr className="border-t border-border">
              <td className="py-1.5 px-3 font-semibold text-muted-foreground">Total</td>
              <td className="py-1.5 px-3" />
              <td className="py-1.5 px-3 text-right font-semibold text-foreground">{n}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Shared chart constants (match MaeScatter) ─────────────────────────────────

const W = 520
const H = 300
const MX = { top: 24, right: 28, bottom: 52, left: 60 }
const IW = W - MX.left - MX.right
const IH = H - MX.top - MX.bottom

const BUCKETS = [
  { label: "0–2%",   min: 0,  max: 2,        color: "#fbbf24" },
  { label: "2–5%",   min: 2,  max: 5,        color: "#f97316" },
  { label: "5–10%",  min: 5,  max: 10,       color: "#ef4444" },
  { label: "10–20%", min: 10, max: 20,       color: "#dc2626" },
  { label: "20–30%", min: 20, max: 30,       color: "#b91c1c" },
  { label: ">30%",   min: 30, max: Infinity, color: "#7f1d1d" },
]

function bucketColor(depthAbs: number): string {
  if (depthAbs > 30) return "#7f1d1d"
  if (depthAbs > 20) return "#b91c1c"
  if (depthAbs > 10) return "#dc2626"
  if (depthAbs > 5)  return "#ef4444"
  if (depthAbs > 2)  return "#f97316"
  return "#fbbf24"
}

// ── Depth Histogram ───────────────────────────────────────────────────────────

interface HistTooltip {
  label: string
  count: number
  clientX: number
  clientY: number
}

function DepthHistogram({ periods }: { periods: DDPeriod[] }) {
  const [tooltip, setTooltip] = useState<HistTooltip | null>(null)

  const counts = BUCKETS.map(b => ({
    ...b,
    count: periods.filter(p => {
      const abs = Math.abs(p.depthPct)
      return abs >= b.min && abs < b.max
    }).length,
  }))
  const maxCount = Math.max(...counts.map(b => b.count), 1)

  const nBuckets = counts.length
  const rowH = IH / nBuckets
  const barPad = 4

  const xTicks = [0, 0.25, 0.5, 0.75, 1].map(f => Math.round(f * maxCount))

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const svgY = (e.clientY - rect.top) * (H / rect.height) - MX.top
    const idx = Math.floor(svgY / rowH)
    if (idx >= 0 && idx < counts.length) {
      setTooltip({ label: counts[idx].label, count: counts[idx].count, clientX: e.clientX, clientY: e.clientY })
    } else {
      setTooltip(null)
    }
  }

  return (
    <div className="relative">
      <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mt-1 mb-3">
        Depth Distribution
      </h2>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full cursor-crosshair"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
      >
        <g transform={`translate(${MX.left},${MX.top})`}>

          {/* Vertical grid lines */}
          {xTicks.map(v => (
            <line key={v}
              x1={(v / maxCount) * IW} y1={0} x2={(v / maxCount) * IW} y2={IH}
              stroke="#000" strokeOpacity={0.15} strokeWidth={1} />
          ))}

          {/* Horizontal bars */}
          {counts.map((b, i) => {
            const barW = (b.count / maxCount) * IW
            const y = i * rowH + barPad
            const bH = rowH - barPad * 2
            return (
              <g key={b.label}>
                <rect x={0} y={y} width={barW || 0} height={bH}
                  fill={b.color} fillOpacity={0.7} rx={2} />
                <text x={-6} y={y + bH / 2 + 4} textAnchor="end" fontSize={10}
                  fill="hsl(var(--muted-foreground))">
                  {b.label}
                </text>
                {b.count > 0 && (
                  <text x={barW + 5} y={y + bH / 2 + 4} fontSize={10}
                    fill={b.color} fontWeight="600">
                    {b.count}
                  </text>
                )}
              </g>
            )
          })}

          {/* X tick marks & labels */}
          {xTicks.map(v => (
            <g key={v}>
              <line x1={(v / maxCount) * IW} y1={IH} x2={(v / maxCount) * IW} y2={IH + 5}
                stroke="hsl(var(--muted-foreground))" strokeWidth={1} />
              <text x={(v / maxCount) * IW} y={IH + 18} textAnchor="middle" fontSize={10}
                fill="hsl(var(--muted-foreground))">{v}</text>
            </g>
          ))}
          <text x={IW / 2} y={IH + 40} textAnchor="middle" fontSize={11}
            fill="hsl(var(--foreground))" fontWeight="500">Count</text>

          {/* Axes */}
          <line x1={0} y1={IH} x2={IW} y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />
          <line x1={0} y1={0} x2={0} y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />

        </g>
      </svg>

      {tooltip && (
        <div
          className="pointer-events-none fixed z-50 rounded border border-border bg-popover px-3 py-2 text-xs shadow-lg"
          style={{ left: tooltip.clientX + 14, top: tooltip.clientY - 40 }}
        >
          <div className="font-semibold text-foreground mb-1">{tooltip.label}</div>
          <div className="text-muted-foreground">
            Count: <span className="text-foreground font-medium">{tooltip.count}</span>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Depth vs Recovery Scatter ─────────────────────────────────────────────────

interface ScatterPoint {
  depth: number
  recovery: number
  startDate: string
}

interface ScatterTooltip {
  point: ScatterPoint
  clientX: number
  clientY: number
}

function DepthVsRecovery({ periods }: { periods: DDPeriod[] }) {
  const [tooltip, setTooltip] = useState<ScatterTooltip | null>(null)

  const points: ScatterPoint[] = periods
    .filter(p => p.recoveryDays != null && p.recoveryDays > 0)
    .map(p => ({ depth: Math.abs(p.depthPct), recovery: p.recoveryDays!, startDate: p.startDate }))

  if (points.length < 3) return (
    <div>
      <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mt-1 mb-3">
        Depth vs Recovery
      </h2>
      <p className="text-sm text-muted-foreground italic">Not enough recovered periods.</p>
    </div>
  )

  const maxDepth = Math.max(...points.map(p => p.depth)) * 1.08
  const maxRec   = Math.max(...points.map(p => p.recovery)) * 1.08

  const xs = (v: number) => (v / maxDepth) * IW
  const ys = (v: number) => IH - (v / maxRec) * IH

  const xTicks = [0, 0.25, 0.5, 0.75, 1].map(f => Math.round(f * Math.max(...points.map(p => p.depth))))
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map(f => Math.round(f * Math.max(...points.map(p => p.recovery))))

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const svgX = (e.clientX - rect.left) * (W / rect.width) - MX.left
    const svgY = (e.clientY - rect.top) * (H / rect.height) - MX.top

    let nearest: ScatterPoint | null = null
    let minDist = Infinity
    for (const p of points) {
      const d = Math.hypot(svgX - xs(p.depth), svgY - ys(p.recovery))
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
      <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mt-1 mb-3">
        Depth vs Recovery — Closed Drawdowns
      </h2>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full cursor-crosshair"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
      >
        <g transform={`translate(${MX.left},${MX.top})`}>

          {/* Grid */}
          {yTicks.map(v => (
            <line key={`gy${v}`}
              x1={0} y1={ys(v)} x2={IW} y2={ys(v)}
              stroke="#000" strokeOpacity={0.15} strokeWidth={1} />
          ))}
          {xTicks.map(v => (
            <line key={`gx${v}`}
              x1={xs(v)} y1={0} x2={xs(v)} y2={IH}
              stroke="#000" strokeOpacity={0.15} strokeWidth={1} />
          ))}

          {/* Dots */}
          {points.map((p, i) => {
            const col = bucketColor(p.depth)
            return (
              <circle key={i}
                cx={xs(p.depth)} cy={ys(p.recovery)} r={4}
                fill={col} fillOpacity={0.65}
                stroke={col} strokeWidth={0.8}
              />
            )
          })}

          {/* Highlighted dot */}
          {tooltip && (
            <circle
              cx={xs(tooltip.point.depth)} cy={ys(tooltip.point.recovery)} r={6}
              fill="none" stroke={bucketColor(tooltip.point.depth)} strokeWidth={2}
            />
          )}

          {/* Axes */}
          <line x1={0} y1={IH} x2={IW} y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />
          <line x1={0} y1={0} x2={0} y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />

          {/* X ticks */}
          {xTicks.map(v => (
            <g key={`xt${v}`}>
              <line x1={xs(v)} y1={IH} x2={xs(v)} y2={IH + 5}
                stroke="hsl(var(--muted-foreground))" strokeWidth={1} />
              <text x={xs(v)} y={IH + 18} textAnchor="middle" fontSize={10}
                fill="hsl(var(--muted-foreground))">-{v}%</text>
            </g>
          ))}
          <text x={IW / 2} y={IH + 40} textAnchor="middle" fontSize={11}
            fill="hsl(var(--foreground))" fontWeight="500">Depth (%)</text>

          {/* Y ticks */}
          {yTicks.map(v => (
            <g key={`yt${v}`}>
              <line x1={0} y1={ys(v)} x2={-5} y2={ys(v)}
                stroke="hsl(var(--muted-foreground))" strokeWidth={1} />
              <text x={-10} y={ys(v) + 3.5} textAnchor="end" fontSize={10}
                fill="hsl(var(--muted-foreground))">{v}d</text>
            </g>
          ))}
          <text
            x={-(IH / 2)} y={-44}
            textAnchor="middle" fontSize={11} fill="hsl(var(--foreground))" fontWeight="500"
            transform="rotate(-90)"
          >
            Recovery (days)
          </text>

        </g>
      </svg>

      {tooltip && (
        <div
          className="pointer-events-none fixed z-50 rounded border border-border bg-popover px-3 py-2 text-xs shadow-lg"
          style={{ left: tooltip.clientX + 14, top: tooltip.clientY - 40 }}
        >
          <div className="font-semibold mb-1" style={{ color: bucketColor(tooltip.point.depth) }}>
            -{tooltip.point.depth.toFixed(1)}% depth
          </div>
          <div className="text-muted-foreground">
            Recovery: <span className="text-foreground font-medium">{tooltip.point.recovery}d</span>
          </div>
          <div className="mt-1 text-muted-foreground/60">{tooltip.point.startDate}</div>
        </div>
      )}

      <div className="mt-1.5 flex gap-3 text-xs text-muted-foreground px-1 flex-wrap">
        {BUCKETS.map(b => (
          <span key={b.label} className="flex items-center gap-1.5">
            <span className="inline-block w-2.5 h-2.5 rounded-full opacity-70"
              style={{ backgroundColor: b.color }} />
            {b.label}
          </span>
        ))}
      </div>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export function DrawdownAnalysis({ equityStrategy, label = "Strategy" }: Props) {
  const periods = useMemo(() => computeAllPeriods(equityStrategy), [equityStrategy])

  if (periods.length < 2) return null

  return (
    <div className="space-y-4">
      <SectionTitle>Drawdown Analysis — {label} — {periods.length} periods</SectionTitle>
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        <DepthDistributionTable periods={periods} />
        <DepthHistogram periods={periods} />
        <DepthVsRecovery periods={periods} />
      </div>
    </div>
  )
}
