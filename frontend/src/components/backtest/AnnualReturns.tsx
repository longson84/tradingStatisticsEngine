import { useMemo, useState } from "react"

interface Props {
  equityStrategy: Record<string, number>
  equityBah: Record<string, number>
  strategyLabel: string
}

interface TooltipState {
  year: string
  strat: number
  bah: number
  clientX: number
  clientY: number
}

const W = 520
const H = 240
const MX = { top: 20, right: 20, bottom: 44, left: 56 }
const IW = W - MX.left - MX.right
const IH = H - MX.top - MX.bottom

function computeAnnual(curve: Record<string, number>): Record<string, number> {
  const byYear: Record<string, { first: number; last: number }> = {}
  for (const [date, value] of Object.entries(curve).sort(([a], [b]) => a.localeCompare(b))) {
    const year = date.slice(0, 4)
    if (!byYear[year]) byYear[year] = { first: value, last: value }
    else byYear[year].last = value
  }
  return Object.fromEntries(
    Object.entries(byYear).map(([year, { first, last }]) => [year, (last / first - 1) * 100])
  )
}

function niceTicks(min: number, max: number, n = 6): number[] {
  const step = (max - min) / (n - 1)
  const nice = Math.pow(10, Math.floor(Math.log10(Math.abs(step) || 1)))
  const rounded = Math.ceil(step / nice) * nice
  const start = Math.floor(min / rounded) * rounded
  const ticks: number[] = []
  for (let v = start; v <= max + rounded * 0.01; v += rounded)
    ticks.push(Math.round(v * 10) / 10)
  return ticks.filter(v => v >= min && v <= max)
}

function signedLog(x: number): number {
  return Math.sign(x) * Math.log10(1 + Math.abs(x))
}

export function AnnualReturns({ equityStrategy, equityBah, strategyLabel }: Props) {
  const [logScale, setLogScale] = useState(false)
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)

  const stratAnnual = useMemo(() => computeAnnual(equityStrategy), [equityStrategy])
  const bahAnnual   = useMemo(() => computeAnnual(equityBah),      [equityBah])

  const years = Object.keys(stratAnnual).sort()
  if (years.length === 0) return null

  const allVals  = [...Object.values(stratAnnual), ...Object.values(bahAnnual)]
  const rawYMin  = Math.min(0, Math.min(...allVals)) * 1.12
  const rawYMax  = Math.max(0, Math.max(...allVals)) * 1.12

  const yTransform = logScale ? signedLog : (x: number) => x
  const yMin = yTransform(rawYMin)
  const yMax = yTransform(rawYMax)

  const ys = (v: number) => IH - ((yTransform(v) - yMin) / (yMax - yMin)) * IH
  const y0 = ys(0)
  const bh = (v: number) => Math.abs(ys(v) - y0)

  const slotW = IW / years.length
  const barW  = Math.min(slotW * 0.36, 18)
  const gap   = 2

  const yTicks = niceTicks(rawYMin, rawYMax, 7)

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mt-1">
          Annual Returns
        </h2>
        <button
          onClick={() => setLogScale(s => !s)}
          className={`px-2.5 py-1 rounded border text-xs transition-colors ${
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
        className="w-full cursor-default"
        onMouseLeave={() => setTooltip(null)}
      >
        <g transform={`translate(${MX.left},${MX.top})`}>

          {/* Grid */}
          {yTicks.map(v => (
            <line key={v} x1={0} y1={ys(v)} x2={IW} y2={ys(v)}
              stroke="#000" strokeOpacity={0.1} strokeWidth={1} />
          ))}

          {/* Bars */}
          {years.map((year, i) => {
            const cx    = i * slotW + slotW / 2
            const sVal  = stratAnnual[year] ?? 0
            const bVal  = bahAnnual[year]   ?? 0
            const hov   = tooltip?.year === year

            const sx   = cx - barW - gap / 2
            const sTop = sVal >= 0 ? ys(sVal) : y0
            const sH   = bh(sVal)

            const bx   = cx + gap / 2
            const bTop = bVal >= 0 ? ys(bVal) : y0
            const bHH  = bh(bVal)

            return (
              <g
                key={year}
                onMouseEnter={e => setTooltip({ year, strat: sVal, bah: bVal, clientX: e.clientX, clientY: e.clientY })}
                onMouseMove={e => setTooltip(s => s ? { ...s, clientX: e.clientX, clientY: e.clientY } : null)}
                style={{ cursor: "pointer" }}
              >
                {/* Strategy bar */}
                <rect x={sx} y={sTop} width={barW} height={Math.max(sH, 1)}
                  fill={sVal >= 0 ? "rgba(59,130,246,0.80)" : "rgba(239,68,68,0.65)"}
                  fillOpacity={hov ? 1 : 0.85}
                  rx={2} />
                {/* B&H bar */}
                <rect x={bx} y={bTop} width={barW} height={Math.max(bHH, 1)}
                  fill={bVal >= 0 ? "rgba(107,114,128,0.55)" : "rgba(239,68,68,0.35)"}
                  fillOpacity={hov ? 1 : 0.85}
                  rx={2} />
              </g>
            )
          })}

          {/* Zero line */}
          <line x1={0} y1={y0} x2={IW} y2={y0}
            stroke="hsl(var(--muted-foreground))" strokeWidth={1.5} />

          {/* Axes */}
          <line x1={0} y1={IH} x2={IW} y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />
          <line x1={0} y1={0}  x2={0}  y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />

          {/* X labels */}
          {years.map((year, i) => (
            <text key={year}
              x={i * slotW + slotW / 2} y={IH + 15}
              textAnchor="middle" fontSize={9} fill="hsl(var(--muted-foreground))">
              {year}
            </text>
          ))}

          {/* Y ticks */}
          {yTicks.map(v => (
            <g key={v}>
              <line x1={0} y1={ys(v)} x2={-4} y2={ys(v)}
                stroke="hsl(var(--muted-foreground))" strokeWidth={1} />
              <text x={-8} y={ys(v) + 3.5} textAnchor="end" fontSize={9}
                fill="hsl(var(--muted-foreground))">{v}%</text>
            </g>
          ))}
          <text x={-(IH / 2)} y={-44} textAnchor="middle" fontSize={10}
            fill="hsl(var(--foreground))" fontWeight="500" transform="rotate(-90)">
            Return %
          </text>

        </g>
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="pointer-events-none fixed z-50 rounded border border-border bg-popover px-3 py-2 text-xs shadow-lg"
          style={{ left: tooltip.clientX + 14, top: tooltip.clientY - 56 }}
        >
          <div className="font-semibold mb-1 text-foreground">{tooltip.year}</div>
          <div className="text-muted-foreground">
            Strategy: <span className={`font-medium ${tooltip.strat >= 0 ? "text-blue-400" : "text-red-400"}`}>
              {(tooltip.strat >= 0 ? "+" : "") + tooltip.strat.toFixed(2)}%
            </span>
          </div>
          <div className="text-muted-foreground">
            B&amp;H: <span className={`font-medium ${tooltip.bah >= 0 ? "text-green-400" : "text-red-400"}`}>
              {(tooltip.bah >= 0 ? "+" : "") + tooltip.bah.toFixed(2)}%
            </span>
          </div>
          <div className="mt-1 text-muted-foreground/60">
            Alpha: <span className={`font-medium ${tooltip.strat - tooltip.bah >= 0 ? "text-green-400" : "text-red-400"}`}>
              {(tooltip.strat - tooltip.bah >= 0 ? "+" : "") + (tooltip.strat - tooltip.bah).toFixed(2)}%
            </span>
          </div>
        </div>
      )}

      <div className="mt-1.5 flex gap-4 text-xs text-muted-foreground px-1">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-blue-500" />{strategyLabel}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-gray-500 opacity-60" />Buy &amp; Hold
        </span>
        <span className="ml-auto text-muted-foreground/50">hover for alpha</span>
      </div>
    </div>
  )
}
