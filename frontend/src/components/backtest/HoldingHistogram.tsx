import { useState } from "react"
import type { TradeRow } from "@/lib/api"

interface Props {
  trades: TradeRow[]
}

interface BinDef {
  label: string
  min: number
  max: number
}

interface BinData extends BinDef {
  total: number
  winners: number
  losers: number
}

interface TooltipState {
  bin: BinData
  clientX: number
  clientY: number
}

const BIN_DEFS: BinDef[] = [
  { label: "1–5d",   min: 1,  max: 5         },
  { label: "6–10d",  min: 6,  max: 10        },
  { label: "11–20d", min: 11, max: 20        },
  { label: "21–40d", min: 21, max: 40        },
  { label: "41–80d", min: 41, max: 80        },
  { label: "81+d",   min: 81, max: Infinity  },
]

const W = 460
const H = 260
const MX = { top: 24, right: 16, bottom: 48, left: 44 }
const IW = W - MX.left - MX.right
const IH = H - MX.top - MX.bottom

function niceTicks(max: number, n = 5): number[] {
  const step = max / (n - 1)
  const nice = Math.pow(10, Math.floor(Math.log10(step || 1)))
  const rounded = Math.ceil(step / nice) * nice
  const ticks: number[] = []
  for (let v = 0; v <= max + rounded * 0.01; v += rounded)
    ticks.push(Math.round(v))
  return ticks
}

export function HoldingHistogram({ trades }: Props) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)

  const closed = trades.filter(t => t.holding_days != null && t.exit_date != null)

  if (closed.length === 0) {
    return (
      <div>
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mt-1 mb-3">
          Holding Duration
        </h2>
        <p className="text-sm text-muted-foreground italic">No data.</p>
      </div>
    )
  }

  const bins: BinData[] = BIN_DEFS.map(bin => {
    const inBin = closed.filter(t => t.holding_days! >= bin.min && t.holding_days! <= bin.max)
    const winners = inBin.filter(t => t.return_pct != null && t.return_pct > 0).length
    return { ...bin, total: inBin.length, winners, losers: inBin.length - winners }
  }).filter(b => b.total > 0)

  const maxCount = Math.max(...bins.map(b => b.total))
  const yTicks = niceTicks(maxCount, 5)

  const slotW = IW / bins.length
  const barW = slotW * 0.62

  const bh = (count: number) => (count / maxCount) * IH

  return (
    <div className="relative">
      <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mt-1 mb-2">
        Holding Duration
      </h2>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full cursor-default"
        onMouseLeave={() => setTooltip(null)}
      >
        <g transform={`translate(${MX.left},${MX.top})`}>

          {/* Grid */}
          {yTicks.map(v => (
            <line key={v}
              x1={0} y1={IH - bh(v)} x2={IW} y2={IH - bh(v)}
              stroke="#000" strokeOpacity={0.1} strokeWidth={1}
            />
          ))}

          {/* Bars */}
          {bins.map((bin, i) => {
            const cx = i * slotW + slotW / 2
            const x = cx - barW / 2
            const hovered = tooltip?.bin.label === bin.label
            return (
              <g
                key={bin.label}
                style={{ cursor: "pointer" }}
                onMouseEnter={e => setTooltip({ bin, clientX: e.clientX, clientY: e.clientY })}
                onMouseMove={e => setTooltip(s => s ? { ...s, clientX: e.clientX, clientY: e.clientY } : null)}
              >
                {/* Losers — bottom portion */}
                {bin.losers > 0 && (
                  <rect
                    x={x} y={IH - bh(bin.losers)}
                    width={barW} height={bh(bin.losers)}
                    fill="#ef4444" fillOpacity={hovered ? 0.75 : 0.6}
                    rx={2} ry={2}
                  />
                )}
                {/* Winners — stacked on top */}
                {bin.winners > 0 && (
                  <rect
                    x={x} y={IH - bh(bin.total)}
                    width={barW} height={bh(bin.winners)}
                    fill="#22c55e" fillOpacity={hovered ? 0.8 : 0.65}
                    rx={2} ry={2}
                  />
                )}
                {/* Total count above bar */}
                <text
                  x={cx} y={IH - bh(bin.total) - 5}
                  textAnchor="middle" fontSize={9}
                  fill="hsl(var(--muted-foreground))"
                >
                  {bin.total}
                </text>
              </g>
            )
          })}

          {/* Axes */}
          <line x1={0} y1={IH} x2={IW} y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />
          <line x1={0} y1={0} x2={0} y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />

          {/* Y ticks */}
          {yTicks.filter(v => v > 0).map(v => (
            <g key={v}>
              <line x1={0} y1={IH - bh(v)} x2={-4} y2={IH - bh(v)}
                stroke="hsl(var(--muted-foreground))" strokeWidth={1} />
              <text x={-8} y={IH - bh(v) + 3.5}
                textAnchor="end" fontSize={9} fill="hsl(var(--muted-foreground))">{v}</text>
            </g>
          ))}
          <text
            x={-(IH / 2)} y={-32}
            textAnchor="middle" fontSize={10} fill="hsl(var(--foreground))" fontWeight="500"
            transform="rotate(-90)"
          >
            Trades
          </text>

          {/* X labels */}
          {bins.map((bin, i) => (
            <text
              key={bin.label}
              x={i * slotW + slotW / 2} y={IH + 16}
              textAnchor="middle" fontSize={9} fill="hsl(var(--muted-foreground))"
            >
              {bin.label}
            </text>
          ))}
          <text x={IW / 2} y={IH + 38} textAnchor="middle" fontSize={10}
            fill="hsl(var(--foreground))" fontWeight="500">
            Holding Days
          </text>

        </g>
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="pointer-events-none fixed z-50 rounded border border-border bg-popover px-3 py-2 text-xs shadow-lg"
          style={{ left: tooltip.clientX + 14, top: tooltip.clientY - 56 }}
        >
          <div className="font-semibold mb-1 text-foreground">{tooltip.bin.label}</div>
          <div className="text-muted-foreground">Total: <span className="text-foreground font-medium">{tooltip.bin.total}</span></div>
          <div className="text-muted-foreground">Winners: <span className="text-green-400 font-medium">{tooltip.bin.winners}</span></div>
          <div className="text-muted-foreground">Losers: <span className="text-red-400 font-medium">{tooltip.bin.losers}</span></div>
          <div className="text-muted-foreground">Win rate: <span className="text-foreground font-medium">
            {tooltip.bin.total > 0 ? ((tooltip.bin.winners / tooltip.bin.total) * 100).toFixed(0) + "%" : "—"}
          </span></div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-1.5 flex gap-4 text-xs text-muted-foreground px-1">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-green-500 opacity-70" />Winners
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-red-500 opacity-70" />Losers
        </span>
      </div>
    </div>
  )
}
