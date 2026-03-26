import { useState } from "react"
import type { TradeRow } from "@/lib/api"

interface Props {
  trades: TradeRow[]
}

interface Point {
  days: number
  ret: number
  mae: number | null
  mfe: number | null
  win: boolean
  entryDate: string
  exitDate: string
}

interface Tooltip {
  point: Point
  clientX: number
  clientY: number
}

const W = 520
const H = 300
const MX = { top: 24, right: 28, bottom: 52, left: 60 }
const IW = W - MX.left - MX.right
const IH = H - MX.top - MX.bottom

function signedLog(x: number): number {
  return Math.sign(x) * Math.log10(1 + Math.abs(x))
}

function niceTicks(min: number, max: number, n = 6): number[] {
  const step = (max - min) / (n - 1)
  const nice = Math.pow(10, Math.floor(Math.log10(Math.abs(step) || 1)))
  const rounded = Math.ceil(step / nice) * nice
  const start = Math.floor(min / rounded) * rounded
  const ticks: number[] = []
  for (let v = start; v <= max + rounded * 0.01; v += rounded)
    ticks.push(Math.round(v * 10) / 10)
  return ticks
}

function fmt(n: number): string {
  return (n >= 0 ? "+" : "") + n.toFixed(2) + "%"
}

export function ReturnVsDuration({ trades }: Props) {
  const [logScale, setLogScale] = useState(false)
  const [tooltip, setTooltip] = useState<Tooltip | null>(null)

  const points: Point[] = trades
    .filter(t => t.holding_days != null && t.return_pct != null && t.exit_date != null)
    .map(t => ({
      days: t.holding_days!,
      ret: t.return_pct!,
      mae: t.mae_pct ?? null,
      mfe: t.mfe_pct ?? null,
      win: t.return_pct! > 0,
      entryDate: t.entry_date,
      exitDate: t.exit_date!,
    }))

  if (points.length === 0) {
    return (
      <div>
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mt-1 mb-3">
          Return vs Duration
        </h2>
        <p className="text-sm text-muted-foreground italic">No data.</p>
      </div>
    )
  }

  const xMax = Math.max(...points.map(p => p.days)) * 1.06
  const rawYMin = Math.min(...points.map(p => p.ret)) * 1.08
  const rawYMax = Math.max(...points.map(p => p.ret)) * 1.08

  const yTransform = logScale ? signedLog : (x: number) => x
  const yMin = yTransform(rawYMin)
  const yMax = yTransform(rawYMax)

  const xs = (v: number) => (v / xMax) * IW
  const ys = (v: number) => IH - ((yTransform(v) - yMin) / (yMax - yMin)) * IH
  const y0 = ys(0)

  const xTicks = niceTicks(0, xMax, 6)
  const yTicks = niceTicks(rawYMin, rawYMax, 7).filter(v => v >= rawYMin && v <= rawYMax)

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const svgX = (e.clientX - rect.left) * (W / rect.width) - MX.left
    const svgY = (e.clientY - rect.top) * (H / rect.height) - MX.top
    let nearest: Point | null = null
    let minDist = Infinity
    for (const p of points) {
      const d = Math.hypot(svgX - xs(p.days), svgY - ys(p.ret))
      if (d < minDist) { minDist = d; nearest = p }
    }
    if (nearest && minDist < 18) setTooltip({ point: nearest, clientX: e.clientX, clientY: e.clientY })
    else setTooltip(null)
  }

  return (
    <div className="relative max-w-4xl">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mt-1">
          Return vs Duration
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
        className="w-full cursor-crosshair"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
      >
        <g transform={`translate(${MX.left},${MX.top})`}>

          {/* Grid */}
          {yTicks.map(v => (
            <line key={`gy${v}`}
              x1={0} y1={ys(v)} x2={IW} y2={ys(v)}
              stroke="#000" strokeOpacity={0.1} strokeWidth={1} />
          ))}
          {xTicks.map(v => (
            <line key={`gx${v}`}
              x1={xs(v)} y1={0} x2={xs(v)} y2={IH}
              stroke="#000" strokeOpacity={0.1} strokeWidth={1} />
          ))}

          {/* Zero return line */}
          <line x1={0} y1={y0} x2={IW} y2={y0}
            stroke="hsl(var(--muted-foreground))" strokeDasharray="5,3" strokeWidth={1.2} />

          {/* Dots */}
          {points.map((p, i) => (
            <circle key={i}
              cx={xs(p.days)} cy={ys(p.ret)} r={4}
              fill={p.win ? "#22c55e" : "#ef4444"}
              fillOpacity={0.65}
              stroke={p.win ? "#16a34a" : "#b91c1c"}
              strokeWidth={0.8}
            />
          ))}

          {/* Highlighted dot */}
          {tooltip && (
            <circle
              cx={xs(tooltip.point.days)} cy={ys(tooltip.point.ret)} r={6}
              fill="none"
              stroke={tooltip.point.win ? "#4ade80" : "#f87171"}
              strokeWidth={2}
            />
          )}

          {/* Axes */}
          <line x1={0} y1={IH} x2={IW} y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />
          <line x1={0} y1={0} x2={0} y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />

          {/* X ticks */}
          {xTicks.map(v => (
            <g key={`xt${v}`}>
              <line x1={xs(v)} y1={IH} x2={xs(v)} y2={IH + 4}
                stroke="hsl(var(--muted-foreground))" strokeWidth={1} />
              <text x={xs(v)} y={IH + 15} textAnchor="middle" fontSize={9}
                fill="hsl(var(--muted-foreground))">{v}d</text>
            </g>
          ))}
          <text x={IW / 2} y={IH + 38} textAnchor="middle" fontSize={10}
            fill="hsl(var(--foreground))" fontWeight="500">
            Holding Days
          </text>

          {/* Y ticks */}
          {yTicks.map(v => (
            <g key={`yt${v}`}>
              <line x1={0} y1={ys(v)} x2={-4} y2={ys(v)}
                stroke="hsl(var(--muted-foreground))" strokeWidth={1} />
              <text x={-8} y={ys(v) + 3.5} textAnchor="end" fontSize={9}
                fill="hsl(var(--muted-foreground))">{v}%</text>
            </g>
          ))}
          <text
            x={-(IH / 2)} y={-44}
            textAnchor="middle" fontSize={10} fill="hsl(var(--foreground))" fontWeight="500"
            transform="rotate(-90)"
          >
            Return %
          </text>

        </g>
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="pointer-events-none fixed z-50 rounded border border-border bg-popover px-3 py-2 text-xs shadow-lg"
          style={{ left: tooltip.clientX + 14, top: tooltip.clientY - 60 }}
        >
          <div className={`font-semibold mb-1 ${tooltip.point.win ? "text-green-400" : "text-red-400"}`}>
            {tooltip.point.win ? "Winner" : "Loser"}
          </div>
          <div className="text-muted-foreground">Days: <span className="text-foreground font-medium">{tooltip.point.days}</span></div>
          <div className="text-muted-foreground">Return: <span className={`font-medium ${tooltip.point.win ? "text-green-400" : "text-red-400"}`}>{fmt(tooltip.point.ret)}</span></div>
          {tooltip.point.mae != null && (
            <div className="text-muted-foreground">MAE: <span className="text-red-400 font-medium">{tooltip.point.mae.toFixed(2)}%</span></div>
          )}
          {tooltip.point.mfe != null && (
            <div className="text-muted-foreground">MFE: <span className="text-green-400 font-medium">+{tooltip.point.mfe.toFixed(2)}%</span></div>
          )}
          <div className="mt-1 text-muted-foreground/60">{tooltip.point.entryDate} → {tooltip.point.exitDate}</div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-1.5 flex gap-4 text-xs text-muted-foreground px-1">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-green-500 opacity-70" />Winners
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-red-500 opacity-70" />Losers
        </span>
      </div>
    </div>
  )
}
