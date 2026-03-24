import { useMemo } from "react"
import type { TradeRow } from "@/lib/api"
import { SectionTitle } from "./SectionTitle"

interface Props {
  trades: TradeRow[]
}

const W = 480
const H = 220
const MX = { top: 12, right: 12, bottom: 36, left: 36 }
const IW = W - MX.left - MX.right
const IH = H - MX.top - MX.bottom

function bucketSize(range: number): number {
  if (range <= 20) return 1
  if (range <= 50) return 2
  if (range <= 100) return 5
  return 10
}

export function ReturnHistogram({ trades }: Props) {
  const returns = trades
    .filter(t => t.return_pct != null && t.exit_date != null)
    .map(t => t.return_pct!)

  const { buckets, bSize } = useMemo(() => {
    if (returns.length === 0) return { buckets: [], bSize: 5 }
    const range = Math.max(...returns) - Math.min(...returns)
    const bSize = bucketSize(range)
    const lo0 = Math.floor(Math.min(...returns) / bSize) * bSize
    const hi0 = Math.ceil(Math.max(...returns) / bSize) * bSize
    const buckets: { lo: number; hi: number; count: number }[] = []
    for (let lo = lo0; lo < hi0; lo += bSize) {
      const hi = lo + bSize
      const count = returns.filter(r => r >= lo && r < hi).length
      buckets.push({ lo, hi, count })
    }
    // last bucket is inclusive on right edge
    if (buckets.length > 0) {
      const last = buckets[buckets.length - 1]
      last.count += returns.filter(r => r === last.hi).length
    }
    return { buckets, bSize }
  }, [returns])

  if (buckets.length === 0) {
    return (
      <div>
        <SectionTitle>Return Distribution</SectionTitle>
        <p className="text-sm text-muted-foreground italic">No data.</p>
      </div>
    )
  }

  const maxCount = Math.max(...buckets.map(b => b.count))
  const barW = IW / buckets.length
  const zeroIdx = buckets.findIndex(b => b.lo >= 0)

  const yTick = (frac: number) => ({ y: IH - frac * IH, val: Math.round(maxCount * frac) })
  const showLabel = (i: number) => buckets.length <= 12 || i % 2 === 0 || i === buckets.length - 1

  return (
    <div>
      <SectionTitle>Return Distribution — {returns.length} Trades</SectionTitle>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full text-[9px]">
        <g transform={`translate(${MX.left},${MX.top})`}>

          {/* Grid lines */}
          {[0.25, 0.5, 0.75, 1].map(f => (
            <line key={f} x1={0} y1={IH - f * IH} x2={IW} y2={IH - f * IH}
              stroke="#1f2937" strokeWidth={1} />
          ))}

          {/* Bars */}
          {buckets.map((b, i) => {
            const bh = maxCount > 0 ? (b.count / maxCount) * IH : 0
            return (
              <rect key={i}
                x={i * barW + 1} y={IH - bh}
                width={Math.max(barW - 2, 1)} height={bh}
                fill={b.lo + bSize / 2 >= 0 ? "#22c55e" : "#ef4444"}
                fillOpacity={0.65}
              />
            )
          })}

          {/* Zero divider */}
          {zeroIdx >= 0 && (
            <line x1={zeroIdx * barW} y1={0} x2={zeroIdx * barW} y2={IH}
              stroke="#6b7280" strokeDasharray="3,2" strokeWidth={0.8} />
          )}

          {/* X axis */}
          <line x1={0} y1={IH} x2={IW} y2={IH} stroke="#374151" />
          {buckets.map((b, i) => showLabel(i) && (
            <text key={i}
              x={i * barW + barW / 2} y={IH + 14}
              textAnchor="middle" fill="#6b7280">
              {b.lo}%
            </text>
          ))}

          {/* Y axis */}
          <line x1={0} y1={0} x2={0} y2={IH} stroke="#374151" />
          {[0, 0.5, 1].map(f => {
            const { y, val } = yTick(f)
            return (
              <g key={f}>
                <line x1={-3} y1={y} x2={0} y2={y} stroke="#374151" />
                <text x={-6} y={y + 3} textAnchor="end" fill="#6b7280">{val}</text>
              </g>
            )
          })}

        </g>
      </svg>
    </div>
  )
}
