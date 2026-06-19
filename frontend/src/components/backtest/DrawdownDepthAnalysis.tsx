import { useMemo, useState } from "react"
import { SectionTitle } from "./SectionTitle"

const DD_MIN_THRESHOLD = 5   // minimum depth % to count as a drawdown period

interface Props {
  equityStrategy: Record<string, number>
  equityBah: Record<string, number>
  strategyLabel: string
  currentDepthPct?: number
}

interface DDPeriod {
  depthPct: number       // negative
  recoveryDays: number | null
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function calDays(d1: string, d2: string) {
  return Math.round((Date.parse(d2) - Date.parse(d1)) / 86_400_000)
}

function computePeriods(curve: Record<string, number>): DDPeriod[] {
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
        if (depth < -DD_MIN_THRESHOLD)
          periods.push({ depthPct: depth, recoveryDays: calDays(troughDate, date) })
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
    if (depth < -DD_MIN_THRESHOLD)
      periods.push({ depthPct: depth, recoveryDays: null })
  }
  // suppress unused warning
  void startDate
  return periods
}

function pctile(arr: number[], p: number): number {
  if (!arr.length) return 0
  const s = [...arr].sort((a, b) => a - b)
  const i = (p / 100) * (s.length - 1)
  const lo = Math.floor(i), hi = Math.ceil(i)
  return s[lo] + (s[hi] - s[lo]) * (i - lo)
}

function percentileRowForValue(values: number[], percentiles: number[], current: number | null): number | null {
  if (current == null || !values.length) return null
  const rows = percentiles.map(p => ({ percentile: p, value: pctile(values, p) }))
  const match = rows.find(row => current <= row.value)
  return match?.percentile ?? rows[rows.length - 1].percentile
}

// ── Depth Distribution Table ──────────────────────────────────────────────────

const DEPTH_PCTS = [50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 98]
const SATURATE_AT = 30

function stratHeat(val: number): React.CSSProperties {
  const intensity = Math.min(val / SATURATE_AT, 1)
  return {
    color: intensity > 0.5 ? "#1d4ed8" : "#2563eb",
    backgroundColor: `rgba(59, 130, 246, ${0.08 + intensity * 0.35})`,
  }
}

function bahHeat(val: number): React.CSSProperties {
  const intensity = Math.min(val / SATURATE_AT, 1)
  return {
    color: intensity > 0.4 ? "#b91c1c" : "#dc2626",
    backgroundColor: `rgba(239, 68, 68, ${0.08 + intensity * 0.38})`,
  }
}

function DepthTable({
  stratPeriods, bahPeriods, strategyLabel, currentDepth,
}: {
  stratPeriods: DDPeriod[]
  bahPeriods: DDPeriod[]
  strategyLabel: string
  currentDepth: number | null
}) {
  const stratDepths = stratPeriods.map(p => Math.abs(p.depthPct))
  const bahDepths   = bahPeriods.map(p => Math.abs(p.depthPct))
  const currentPercentile = percentileRowForValue(stratDepths, DEPTH_PCTS, currentDepth)

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs tabular-nums border-collapse">
          <thead>
            <tr className="border-b border-border text-muted-foreground uppercase tracking-wide">
              <th className="py-2 px-3 text-left font-medium">Depth (%)</th>
              <th className="py-2 px-3 text-right font-medium">Strategy</th>
              <th className="py-2 px-3 text-right font-medium">Count</th>
              <th className="py-2 px-3 text-right font-medium border-l border-border">Buy &amp; Hold</th>
              <th className="py-2 px-3 text-right font-medium">Count</th>
            </tr>
          </thead>
          <tbody>
            {DEPTH_PCTS.map(p => {
              const sv = pctile(stratDepths, p)
              const bv = pctile(bahDepths, p)
              const sc = Math.round((p / 100) * stratDepths.length)
              const bc = Math.round((p / 100) * bahDepths.length)
              const isMedian = p === 50
              const isCurrent = p === currentPercentile
              return (
                <tr
                  key={p}
                  className={[
                    "border-b border-border/40",
                    isMedian ? "border-t border-border/60" : "",
                    isCurrent ? "bg-amber-500/12 ring-1 ring-inset ring-amber-500/35" : "",
                  ].join(" ")}
                >
                  <td className={`py-1.5 px-3 ${isMedian || isCurrent ? "font-semibold text-foreground" : "text-muted-foreground"}`}>
                    P{p}
                    {isMedian && (
                      <span className="ml-1.5 text-[9px] text-muted-foreground/60 font-normal uppercase tracking-wider">
                        median
                      </span>
                    )}
                    {isCurrent && (
                      <span className="ml-1.5 rounded bg-amber-500/18 px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-300">
                        current
                      </span>
                    )}
                  </td>
                  <td
                    className={`py-1.5 px-3 text-right ${isMedian || isCurrent ? "font-bold" : "font-medium"}`}
                    style={stratHeat(sv)}
                  >
                    -{sv.toFixed(1)}%
                  </td>
                  <td className={`py-1.5 px-3 text-right ${isMedian || isCurrent ? "font-semibold text-foreground" : "text-foreground"}`}>
                    {sc}
                  </td>
                  <td
                    className={`py-1.5 px-3 text-right border-l border-border ${isMedian ? "font-bold" : "font-medium"}`}
                    style={bahHeat(bv)}
                  >
                    -{bv.toFixed(1)}%
                  </td>
                  <td className={`py-1.5 px-3 text-right ${isMedian ? "font-semibold text-foreground" : "text-foreground"}`}>
                    {bc}
                  </td>
                </tr>
              )
            })}
            <tr className="border-t border-border">
              <td className="py-1.5 px-3 font-semibold text-muted-foreground">Total periods</td>
              <td className="py-1.5 px-3" />
              <td className="py-1.5 px-3 text-right font-semibold text-foreground">{stratPeriods.length}</td>
              <td className="py-1.5 px-3 border-l border-border" />
              <td className="py-1.5 px-3 text-right font-semibold text-foreground">{bahPeriods.length}</td>
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
  { label: `${DD_MIN_THRESHOLD}–10%`, min: DD_MIN_THRESHOLD, max: 10,       stratColor: "#2563eb", bahColor: "#ef4444" },
  { label: "10–20%",                  min: 10,               max: 20,       stratColor: "#1d4ed8", bahColor: "#dc2626" },
  { label: "20–30%",                  min: 20,               max: 30,       stratColor: "#1e40af", bahColor: "#b91c1c" },
  { label: ">30%",                    min: 30,               max: Infinity, stratColor: "#1e3a8a", bahColor: "#7f1d1d" },
]

// ── Depth Distribution Histogram ──────────────────────────────────────────────

interface HistTooltip {
  label: string
  strat: number
  bah: number
  clientX: number
  clientY: number
}

function DepthHistogram({
  stratPeriods, bahPeriods, strategyLabel, currentDepth,
}: {
  stratPeriods: DDPeriod[]
  bahPeriods: DDPeriod[]
  strategyLabel: string
  currentDepth: number | null
}) {
  const [tooltip, setTooltip] = useState<HistTooltip | null>(null)

  const counts = BUCKETS.map(b => ({
    ...b,
    strat: stratPeriods.filter(p => { const a = Math.abs(p.depthPct); return a >= b.min && a < b.max }).length,
    bah:   bahPeriods.filter(p =>   { const a = Math.abs(p.depthPct); return a >= b.min && a < b.max }).length,
  }))
  const currentBucketIndex = currentDepth == null
    ? -1
    : currentDepth < DD_MIN_THRESHOLD
      ? 0
      : counts.findIndex(b => currentDepth >= b.min && currentDepth < b.max)
  const maxCount = Math.max(...counts.flatMap(b => [b.strat, b.bah]), 1)

  const nBuckets = counts.length
  const rowH = IH / nBuckets
  const barPad = 3
  const barH = (rowH - barPad * 3) / 2

  const xTicks = [0, 0.25, 0.5, 0.75, 1].map(f => Math.round(f * maxCount))

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const svgY = (e.clientY - rect.top) * (H / rect.height) - MX.top
    const idx = Math.floor(svgY / rowH)
    if (idx >= 0 && idx < counts.length) {
      const b = counts[idx]
      setTooltip({ label: b.label, strat: b.strat, bah: b.bah, clientX: e.clientX, clientY: e.clientY })
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

          {xTicks.map(v => (
            <line key={v}
              x1={(v / maxCount) * IW} y1={0} x2={(v / maxCount) * IW} y2={IH}
              stroke="#000" strokeOpacity={0.15} strokeWidth={1} />
          ))}

          {counts.map((b, i) => {
            const y0 = i * rowH + barPad
            const y1 = y0 + barH + barPad
            const stratW = (b.strat / maxCount) * IW
            const bahW   = (b.bah   / maxCount) * IW
            const midY   = i * rowH + rowH / 2
            const isCurrent = i === currentBucketIndex
            return (
              <g key={b.label}>
                {isCurrent && (
                  <>
                    <rect
                      x={-MX.left + 2}
                      y={i * rowH + 1}
                      width={IW + MX.left + MX.right - 4}
                      height={rowH - 2}
                      fill="#f59e0b"
                      fillOpacity={0.1}
                      rx={3}
                    />
                    <line
                      x1={0}
                      y1={midY}
                      x2={IW}
                      y2={midY}
                      stroke="#d97706"
                      strokeWidth={1.5}
                      strokeDasharray="4 3"
                    />
                    {currentDepth != null && (
                      <text
                        x={IW - 4}
                        y={midY - 6}
                        textAnchor="end"
                        fontSize={10}
                        fill="#b45309"
                        fontWeight="700"
                      >
                        Current -{currentDepth.toFixed(1)}%
                        {currentDepth < DD_MIN_THRESHOLD ? " (<5%)" : ""}
                      </text>
                    )}
                  </>
                )}
                <rect x={0} y={y0} width={stratW || 0} height={barH}
                  fill={b.stratColor} fillOpacity={0.75} rx={2} />
                {b.strat > 0 && (
                  <text x={stratW + 4} y={y0 + barH / 2 + 3.5} fontSize={9}
                    fill={b.stratColor} fontWeight="600">{b.strat}</text>
                )}

                <rect x={0} y={y1} width={bahW || 0} height={barH}
                  fill={b.bahColor} fillOpacity={0.75} rx={2} />
                {b.bah > 0 && (
                  <text x={bahW + 4} y={y1 + barH / 2 + 3.5} fontSize={9}
                    fill={b.bahColor} fontWeight="600">{b.bah}</text>
                )}

                <text x={-6} y={midY + 4} textAnchor="end" fontSize={10}
                  fill="hsl(var(--muted-foreground))">{b.label}</text>
              </g>
            )
          })}

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
            Strategy: <span className="font-medium text-blue-400">{tooltip.strat}</span>
          </div>
          <div className="text-muted-foreground">
            Buy &amp; Hold: <span className="font-medium text-red-400">{tooltip.bah}</span>
          </div>
        </div>
      )}

      <div className="mt-1.5 flex gap-4 text-xs text-muted-foreground px-1">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm opacity-80 bg-blue-500" />
          Strategy
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm opacity-80 bg-red-500" />
          Buy &amp; Hold
        </span>
      </div>
    </div>
  )
}

// ── Depth vs Recovery Scatter ─────────────────────────────────────────────────

interface ScatterPoint {
  depth: number
  recovery: number
  isStrat: boolean
}

interface ScatterTooltip {
  point: ScatterPoint
  clientX: number
  clientY: number
}

function DepthVsRecovery({
  stratPeriods, bahPeriods, strategyLabel,
}: {
  stratPeriods: DDPeriod[]
  bahPeriods: DDPeriod[]
  strategyLabel: string
}) {
  const [tooltip, setTooltip] = useState<ScatterTooltip | null>(null)

  const stratPoints: ScatterPoint[] = stratPeriods
    .filter(p => p.recoveryDays != null && p.recoveryDays > 0)
    .map(p => ({ depth: Math.abs(p.depthPct), recovery: p.recoveryDays!, isStrat: true }))

  const bahPoints: ScatterPoint[] = bahPeriods
    .filter(p => p.recoveryDays != null && p.recoveryDays > 0)
    .map(p => ({ depth: Math.abs(p.depthPct), recovery: p.recoveryDays!, isStrat: false }))

  const allPoints = [...stratPoints, ...bahPoints]

  if (allPoints.length < 3) return (
    <div>
      <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mt-1 mb-3">
        Depth vs Recovery
      </h2>
      <p className="text-sm text-muted-foreground italic">Not enough recovered periods.</p>
    </div>
  )

  const maxDepth = Math.max(...allPoints.map(p => p.depth)) * 1.08
  const maxRec   = Math.max(...allPoints.map(p => p.recovery)) * 1.08

  const xs = (v: number) => (v / maxDepth) * IW
  const ys = (v: number) => IH - (v / maxRec) * IH

  const xTicks = [0, 0.25, 0.5, 0.75, 1].map(f => Math.round(f * Math.max(...allPoints.map(p => p.depth))))
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map(f => Math.round(f * Math.max(...allPoints.map(p => p.recovery))))

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const svgX = (e.clientX - rect.left) * (W / rect.width) - MX.left
    const svgY = (e.clientY - rect.top) * (H / rect.height) - MX.top

    let nearest: ScatterPoint | null = null
    let minDist = Infinity
    for (const p of allPoints) {
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

          {/* BAH dots behind */}
          {bahPoints.map((p, i) => (
            <circle key={`b${i}`}
              cx={xs(p.depth)} cy={ys(p.recovery)} r={4}
              fill="#f87171" fillOpacity={0.65}
              stroke="#ef4444" strokeWidth={0.8}
            />
          ))}

          {/* Strategy dots on top */}
          {stratPoints.map((p, i) => (
            <circle key={`s${i}`}
              cx={xs(p.depth)} cy={ys(p.recovery)} r={4}
              fill="#60a5fa" fillOpacity={0.65}
              stroke="#3b82f6" strokeWidth={0.8}
            />
          ))}

          {tooltip && (
            <circle
              cx={xs(tooltip.point.depth)} cy={ys(tooltip.point.recovery)} r={6}
              fill="none"
              stroke={tooltip.point.isStrat ? "#3b82f6" : "#ef4444"}
              strokeWidth={2}
            />
          )}

          <line x1={0} y1={IH} x2={IW} y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />
          <line x1={0} y1={0} x2={0} y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />

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
          <div className="font-semibold mb-1"
            style={{ color: tooltip.point.isStrat ? "#60a5fa" : "#f87171" }}>
            {tooltip.point.isStrat ? strategyLabel : "Buy & Hold"}
          </div>
          <div className="text-muted-foreground">
            Depth: <span className="text-foreground font-medium">-{tooltip.point.depth.toFixed(1)}%</span>
          </div>
          <div className="text-muted-foreground">
            Recovery: <span className="text-foreground font-medium">{tooltip.point.recovery}d</span>
          </div>
        </div>
      )}

      <div className="mt-1.5 flex gap-4 text-xs text-muted-foreground px-1">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-blue-400 opacity-70" />
          Strategy
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-red-400 opacity-70" />
          Buy &amp; Hold
        </span>
        <span className="ml-auto text-muted-foreground/50">closed periods only</span>
      </div>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export function DrawdownDepthAnalysis({ equityStrategy, equityBah, strategyLabel, currentDepthPct }: Props) {
  const { stratPeriods, bahPeriods } = useMemo(() => ({
    stratPeriods: computePeriods(equityStrategy),
    bahPeriods:   computePeriods(equityBah),
  }), [equityStrategy, equityBah])
  const currentDepth = currentDepthPct != null && currentDepthPct < 0
    ? Math.abs(currentDepthPct)
    : null

  if (stratPeriods.length < 2 && bahPeriods.length < 2) return null

  return (
    <div className="space-y-4">
      <SectionTitle>Drawdown Depth — Strategy vs Buy &amp; Hold</SectionTitle>
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        <DepthTable stratPeriods={stratPeriods} bahPeriods={bahPeriods} strategyLabel="Strategy" currentDepth={currentDepth} />
        <DepthHistogram stratPeriods={stratPeriods} bahPeriods={bahPeriods} strategyLabel="Strategy" currentDepth={currentDepth} />
        <DepthVsRecovery stratPeriods={stratPeriods} bahPeriods={bahPeriods} strategyLabel="Strategy" />
      </div>
    </div>
  )
}
