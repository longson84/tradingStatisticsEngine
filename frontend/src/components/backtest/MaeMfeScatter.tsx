import { useState } from "react"
import type { TradeRow } from "@/lib/api"

interface Props {
  trades: TradeRow[]
}

interface Point {
  mae: number   // negative (adverse)
  mfe: number
  ret: number | null
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
const MX = { top: 24, right: 60, bottom: 52, left: 28 }
const IW = W - MX.left - MX.right
const IH = H - MX.top - MX.bottom

function safeLog(x: number): number {
  return Math.log10(1 + x)
}

function niceTicks(min: number, max: number, n = 8): number[] {
  const step = (max - min) / (n - 1)
  const nice = Math.pow(10, Math.floor(Math.log10(Math.abs(step) || 1)))
  const rounded = Math.ceil(step / nice) * nice
  const start = Math.floor(min / rounded) * rounded
  const ticks: number[] = []
  for (let v = start; v <= max + rounded * 0.01; v += rounded)
    ticks.push(Math.round(v * 10) / 10)
  return ticks
}

function fmt(n: number, prefix = ""): string {
  return prefix + n.toFixed(2) + "%"
}

export function MaeMfeScatter({ trades }: Props) {
  const [logScale, setLogScale] = useState(false)
  const [tooltip, setTooltip] = useState<Tooltip | null>(null)

  const points: Point[] = trades
    .filter(t => t.mae_pct != null && t.mfe_pct != null && t.exit_date != null)
    .map(t => ({
      mae: t.mae_pct!,   // negative (adverse)
      mfe: t.mfe_pct!,
      ret: t.return_pct ?? null,
      win: t.return_pct != null && t.return_pct > 0,
      entryDate: t.entry_date,
      exitDate: t.exit_date!,
    }))

  if (points.length === 0) {
    return (
      <div>
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mt-1 mb-3">MAE vs MFE</h2>
        <p className="text-sm text-muted-foreground italic">No data.</p>
      </div>
    )
  }

  const yTransform = logScale ? safeLog : (x: number) => x

  const xMin = Math.min(...points.map(p => p.mae)) * 1.08  // negative
  const xMax = Math.abs(xMin) * 0.04                        // small right padding past zero
  const yMax = Math.max(...points.map(p => p.mfe)) * 1.08

  const tyMax = yTransform(yMax)

  const xs = (v: number) => ((v - xMin) / (xMax - xMin)) * IW
  const ys = (v: number) => IH - (yTransform(v) / tyMax) * IH

  const xTicks = niceTicks(xMin, xMax)
  const yTicks = niceTicks(0, yMax)

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const svgX = (e.clientX - rect.left) * (W / rect.width) - MX.left
    const svgY = (e.clientY - rect.top) * (H / rect.height) - MX.top

    let nearest: Point | null = null
    let minDist = Infinity
    for (const p of points) {
      const d = Math.hypot(svgX - xs(p.mae), svgY - ys(p.mfe))
      if (d < minDist) { minDist = d; nearest = p }
    }
    if (nearest && minDist < 18) {
      setTooltip({ point: nearest, clientX: e.clientX, clientY: e.clientY })
    } else {
      setTooltip(null)
    }
  }

  return (
    <div className="relative max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mt-1">
          MAE vs MFE — Closed Trades
        </h2>
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

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full cursor-crosshair"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
      >
        <g transform={`translate(${MX.left},${MX.top})`}>

          {/* Grid lines */}
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
          {points.map((p, i) => (
            <circle key={i}
              cx={xs(p.mae)} cy={ys(p.mfe)} r={4}
              fill={p.win ? "#22c55e" : "#ef4444"}
              fillOpacity={0.65}
              stroke={p.win ? "#16a34a" : "#b91c1c"}
              strokeWidth={0.8}
            />
          ))}

          {/* Highlighted tooltip dot */}
          {tooltip && (
            <circle
              cx={xs(tooltip.point.mae)} cy={ys(tooltip.point.mfe)} r={6}
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
              <text x={xs(v)} y={IH + 18} textAnchor="middle" fontSize={10} fill="hsl(var(--muted-foreground))">{v}%</text>
            </g>
          ))}
          <text x={IW / 2} y={IH + 40} textAnchor="middle" fontSize={11} fill="hsl(var(--foreground))" fontWeight="500">
            MAE %
          </text>

          {/* Y ticks & labels — right side */}
          {yTicks.map(v => (
            <g key={`yt${v}`}>
              <line x1={IW} y1={ys(v)} x2={IW + 5} y2={ys(v)} stroke="hsl(var(--muted-foreground))" strokeWidth={1} />
              <text x={IW + 10} y={ys(v) + 3.5} textAnchor="start" fontSize={10} fill="hsl(var(--muted-foreground))">{v}%</text>
            </g>
          ))}
          <text
            textAnchor="middle" fontSize={11} fill="hsl(var(--foreground))" fontWeight="500"
            transform={`translate(${IW + 44}, ${IH / 2}) rotate(90)`}
          >
            MFE %
          </text>

          {/* Quadrant labels */}
          <text x={4}  y={-6} fontSize={8} fill="hsl(var(--muted-foreground))">low MAE, high MFE — clean trades</text>
          <text x={IW} y={IH + 32} textAnchor="end" fontSize={8} fill="hsl(var(--muted-foreground))">high MAE, low MFE — painful</text>

        </g>
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="pointer-events-none fixed z-50 rounded border border-border bg-popover px-3 py-2 text-xs shadow-lg"
          style={{ left: tooltip.clientX + 14, top: tooltip.clientY - 40 }}
        >
          <div className={`font-semibold mb-1 ${tooltip.point.win ? "text-green-400" : "text-red-400"}`}>
            {tooltip.point.win ? "Winner" : "Loser"}
          </div>
          <div className="text-muted-foreground">MAE: <span className="text-red-400 font-medium">{tooltip.point.mae.toFixed(2)}%</span></div>
          <div className="text-muted-foreground">MFE: <span className="text-green-400 font-medium">+{tooltip.point.mfe.toFixed(2)}%</span></div>
          {tooltip.point.ret != null && (
            <div className="text-muted-foreground">Return: <span className={`font-medium ${tooltip.point.win ? "text-green-400" : "text-red-400"}`}>
              {(tooltip.point.ret >= 0 ? "+" : "") + tooltip.point.ret.toFixed(2)}%
            </span></div>
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
        <span className="ml-auto text-muted-foreground/50">above diagonal = MFE &gt; MAE</span>
      </div>
    </div>
  )
}
