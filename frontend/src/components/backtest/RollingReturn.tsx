import { useMemo, useState } from "react"

interface Props {
  equityStrategy: Record<string, number>
  equityBah: Record<string, number>
}

const W = 520
const H = 240
const MX = { top: 20, right: 28, bottom: 44, left: 60 }
const IW = W - MX.left - MX.right
const IH = H - MX.top - MX.bottom

function computeRolling(curve: Record<string, number>) {
  const sorted = Object.entries(curve).sort(([a], [b]) => a.localeCompare(b))
  const raw: Array<{ date: string; value: number }> = []
  let j = 0

  for (let i = 0; i < sorted.length; i++) {
    const [date, value] = sorted[i]
    const oneYearAgo = new Date(date)
    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1)
    const target = oneYearAgo.toISOString().slice(0, 10)
    while (j + 1 < i && sorted[j + 1][0] <= target) j++
    if (sorted[j][0] <= target) {
      raw.push({ date, value: (value / sorted[j][1] - 1) * 100 })
    }
  }

  // downsample to monthly last-value
  const monthly = new Map<string, { date: string; value: number }>()
  for (const pt of raw) monthly.set(pt.date.slice(0, 7), pt)
  return Array.from(monthly.values())
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

function makePath(data: Array<{ date: string; value: number }>, xs: (d: string) => number, ys: (v: number) => number) {
  return data.map((p, i) => `${i === 0 ? "M" : "L"}${xs(p.date).toFixed(1)},${ys(p.value).toFixed(1)}`).join(" ")
}

function makeArea(data: Array<{ date: string; value: number }>, xs: (d: string) => number, ys: (v: number) => number, y0: number) {
  if (data.length === 0) return ""
  const line = makePath(data, xs, ys)
  return `${line} L${xs(data.at(-1)!.date).toFixed(1)},${y0.toFixed(1)} L${xs(data[0].date).toFixed(1)},${y0.toFixed(1)} Z`
}

function signedLog(x: number): number {
  return Math.sign(x) * Math.log10(1 + Math.abs(x))
}

export function RollingReturn({ equityStrategy, equityBah }: Props) {
  const [logScale, setLogScale] = useState(false)
  const stratData = useMemo(() => computeRolling(equityStrategy), [equityStrategy])
  const bahData   = useMemo(() => computeRolling(equityBah),      [equityBah])

  if (stratData.length === 0) {
    return (
      <div>
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mt-1 mb-3">
          Rolling 12-Month Return
        </h2>
        <p className="text-sm text-muted-foreground italic">Insufficient data (need &gt;1 year).</p>
      </div>
    )
  }

  const allVals  = [...stratData.map(p => p.value), ...bahData.map(p => p.value)]
  const rawYMin  = Math.min(...allVals) * 1.1
  const rawYMax  = Math.max(...allVals) * 1.1
  const firstMs  = Date.parse(stratData[0].date)
  const lastMs   = Date.parse(stratData.at(-1)!.date)
  const dateRange = lastMs - firstMs || 1

  const yTransform = logScale ? signedLog : (x: number) => x
  const yMin = yTransform(rawYMin)
  const yMax = yTransform(rawYMax)

  const xs = (d: string) => ((Date.parse(d) - firstMs) / dateRange) * IW
  const ys = (v: number) => IH - ((yTransform(v) - yMin) / (yMax - yMin)) * IH
  const y0 = ys(0)

  const yTicks = niceTicks(rawYMin, rawYMax, 6)

  // Year labels from stratData
  const yearLabels: Array<{ year: string; x: number }> = []
  for (const p of stratData) {
    if (p.date.slice(5, 7) === "01") yearLabels.push({ year: p.date.slice(0, 4), x: xs(p.date) })
  }

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mt-1">
          Rolling 12-Month Return
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

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        <defs>
          <clipPath id="rrClipPos">
            <rect x={0} y={0} width={IW} height={Math.max(0, y0)} />
          </clipPath>
          <clipPath id="rrClipNeg">
            <rect x={0} y={Math.max(0, y0)} width={IW} height={Math.max(0, IH - y0)} />
          </clipPath>
        </defs>
        <g transform={`translate(${MX.left},${MX.top})`}>

          {/* Grid */}
          {yTicks.map(v => (
            <line key={v} x1={0} y1={ys(v)} x2={IW} y2={ys(v)}
              stroke="#000" strokeOpacity={0.1} strokeWidth={1} />
          ))}

          {/* Area fills — green above 0, red below 0 */}
          <path d={makeArea(stratData, xs, ys, y0)}
            fill="rgba(34,197,94,0.15)" clipPath="url(#rrClipPos)" />
          <path d={makeArea(stratData, xs, ys, y0)}
            fill="rgba(239,68,68,0.15)" clipPath="url(#rrClipNeg)" />

          {/* B&H line */}
          {bahData.length > 0 && (
            <path d={makePath(bahData, xs, ys)} fill="none"
              stroke="#6b7280" strokeWidth={1} strokeDasharray="4,3" strokeOpacity={0.65} />
          )}

          {/* Strategy line */}
          <path d={makePath(stratData, xs, ys)} fill="none"
            stroke="#3b82f6" strokeWidth={1.8} />

          {/* Zero line */}
          <line x1={0} y1={y0} x2={IW} y2={y0}
            stroke="hsl(var(--muted-foreground))" strokeDasharray="4,3" strokeWidth={1} />

          {/* Axes */}
          <line x1={0} y1={IH} x2={IW} y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />
          <line x1={0} y1={0}  x2={0}  y2={IH} stroke="hsl(var(--border))" strokeWidth={1.5} />

          {/* X year labels */}
          {yearLabels.map(({ year, x }) => (
            <g key={year}>
              <line x1={x} y1={IH} x2={x} y2={IH + 4}
                stroke="hsl(var(--muted-foreground))" strokeWidth={1} />
              <text x={x} y={IH + 15} textAnchor="middle" fontSize={9}
                fill="hsl(var(--muted-foreground))">{year}</text>
            </g>
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
            12M Return %
          </text>

        </g>
      </svg>

      <div className="mt-1.5 flex gap-4 text-xs text-muted-foreground px-1">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-4 h-0.5 bg-blue-500" />Strategy
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-4 border-t border-dashed border-gray-500" style={{ height: 0 }} />Buy &amp; Hold
        </span>
        <span className="ml-auto text-muted-foreground/50">above zero = positive trailing year</span>
      </div>
    </div>
  )
}
