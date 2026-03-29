import type { EventStudyZone } from "@/lib/api"

interface Props {
  zones: EventStudyZone[]
}

// Colors per zone — saturated enough for both light/dark
const ZONE_STYLE: Record<number, { stroke: string; fill: string; label: string }> = {
  5:  { stroke: "#dc2626", fill: "rgba(220,38,38,0.12)",  label: "P5" },
  10: { stroke: "#ea580c", fill: "rgba(234,88,12,0.10)",  label: "P10" },
  15: { stroke: "#d97706", fill: "rgba(217,119,6,0.10)",  label: "P15" },
  20: { stroke: "#ca8a04", fill: "rgba(202,138,4,0.08)",  label: "P20" },
  25: { stroke: "#65a30d", fill: "rgba(101,163,13,0.08)", label: "P25" },
}
function zoneStyle(pct: number) {
  return ZONE_STYLE[pct] ?? { stroke: "#9ca3af", fill: "rgba(156,163,175,0.08)", label: `P${pct}` }
}

// Chart layout constants (SVG coordinate space)
const W = 800, H = 260
const M = { top: 20, right: 24, bottom: 44, left: 52 }
const IW = W - M.left - M.right   // 724
const IH = H - M.top  - M.bottom  // 196

const DAY_MIN = -10, DAY_MAX = 90

function xScale(day: number) {
  return M.left + ((day - DAY_MIN) / (DAY_MAX - DAY_MIN)) * IW
}
function yScale(val: number, yMin: number, yMax: number) {
  return M.top + ((yMax - val) / (yMax - yMin)) * IH
}

function pathD(pts: Array<{ day: number; val: number }>, yMin: number, yMax: number) {
  return pts
    .map((p, i) => `${i === 0 ? "M" : "L"}${xScale(p.day).toFixed(1)},${yScale(p.val, yMin, yMax).toFixed(1)}`)
    .join(" ")
}

function bandD(
  paths: EventStudyZone["paths"],
  yMin: number,
  yMax: number,
) {
  const forward  = paths.map(p => ({ day: p.day, val: p.p25 }))
  const backward = [...paths].reverse().map(p => ({ day: p.day, val: p.p75 }))
  return pathD(forward, yMin, yMax) + " " + pathD(backward.map((p, i) => ({ ...p })), yMin, yMax).replace("M", "L") + " Z"
}

const X_TICKS = [-10, 0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
const Y_TICK_COUNT = 6

export function EventStudyChart({ zones }: Props) {
  if (!zones.length) return null

  // Compute y bounds from all zone data
  let yMin = 0, yMax = 0
  zones.forEach(z => z.paths.forEach(p => {
    if (p.p25 < yMin) yMin = p.p25
    if (p.p75 > yMax) yMax = p.p75
    if (p.mean < yMin) yMin = p.mean
    if (p.mean > yMax) yMax = p.mean
  }))
  // Add 15% padding and round to nice numbers
  const range = yMax - yMin || 10
  yMin = Math.floor((yMin - range * 0.15) / 2) * 2
  yMax = Math.ceil((yMax  + range * 0.15) / 2) * 2

  const yStep = ((yMax - yMin) / (Y_TICK_COUNT - 1))
  const yTicks = Array.from({ length: Y_TICK_COUNT }, (_, i) => yMin + i * yStep)

  const x0 = xScale(0)   // vertical line at entry day
  const yZero = yScale(0, yMin, yMax)  // horizontal break-even line

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      {/* Header + legend */}
      <div className="flex items-center gap-4 px-4 py-2 border-b border-border text-[10px] text-muted-foreground flex-wrap">
        <span className="font-medium text-foreground/70 text-xs">Event Study</span>
        <span className="text-muted-foreground/50">Avg price path after zone entry</span>
        <div className="ml-auto flex items-center gap-3">
          {zones.map(z => {
            const s = zoneStyle(z.zone_pct)
            return (
              <span key={z.zone_pct} className="flex items-center gap-1">
                <span
                  className="inline-block w-5 h-0.5 rounded"
                  style={{ backgroundColor: s.stroke }}
                />
                <span style={{ color: s.stroke }} className="font-semibold">
                  {s.label}
                </span>
                <span className="text-muted-foreground/50">({z.count})</span>
              </span>
            )
          })}
        </div>
      </div>

      {/* SVG chart */}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto"
        aria-label="Event study chart"
      >
        {/* Y grid lines + labels */}
        {yTicks.map(val => {
          const y = yScale(val, yMin, yMax)
          return (
            <g key={val}>
              <line
                x1={M.left} y1={y} x2={M.left + IW} y2={y}
                stroke="rgba(128,128,128,0.12)" strokeWidth="1"
              />
              <text
                x={M.left - 6} y={y + 4}
                textAnchor="end"
                fontSize="10"
                fill="#9ca3af"
              >
                {val.toFixed(1)}%
              </text>
            </g>
          )
        })}

        {/* X grid lines + labels */}
        {X_TICKS.map(day => {
          const x = xScale(day)
          return (
            <g key={day}>
              <line
                x1={x} y1={M.top} x2={x} y2={M.top + IH}
                stroke="rgba(128,128,128,0.10)" strokeWidth="1"
              />
              <text
                x={x} y={H - M.bottom + 14}
                textAnchor="middle"
                fontSize="10"
                fill="#9ca3af"
              >
                {day === 0 ? "D0" : day > 0 ? `+${day}` : day}
              </text>
            </g>
          )
        })}

        {/* Break-even line (0%) */}
        <line
          x1={M.left} y1={yZero} x2={M.left + IW} y2={yZero}
          stroke="rgba(156,163,175,0.5)" strokeWidth="1" strokeDasharray="4,3"
        />

        {/* Entry day line (D0) */}
        <line
          x1={x0} y1={M.top} x2={x0} y2={M.top + IH}
          stroke="rgba(156,163,175,0.6)" strokeWidth="1.5" strokeDasharray="5,3"
        />
        <text x={x0 + 4} y={M.top + 12} fontSize="9" fill="#9ca3af">Entry</text>

        {/* Zone bands + mean lines */}
        {zones.map(z => {
          const s = zoneStyle(z.zone_pct)
          const meanPts = z.paths.map(p => ({ day: p.day, val: p.mean }))
          return (
            <g key={z.zone_pct}>
              {/* Shaded band (p25-p75) */}
              <path
                d={bandD(z.paths, yMin, yMax)}
                fill={s.fill}
                stroke="none"
              />
              {/* Mean line */}
              <path
                d={pathD(meanPts, yMin, yMax)}
                fill="none"
                stroke={s.stroke}
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
            </g>
          )
        })}

        {/* Border box */}
        <rect
          x={M.left} y={M.top} width={IW} height={IH}
          fill="none" stroke="rgba(128,128,128,0.20)" strokeWidth="1"
        />

        {/* Axis labels */}
        <text
          x={M.left - 36} y={M.top + IH / 2}
          textAnchor="middle"
          fontSize="10"
          fill="#9ca3af"
          transform={`rotate(-90, ${M.left - 36}, ${M.top + IH / 2})`}
        >
          Return %
        </text>
        <text
          x={M.left + IW / 2} y={H - 4}
          textAnchor="middle"
          fontSize="10"
          fill="#9ca3af"
        >
          Sessions from zone entry
        </text>
      </svg>
    </div>
  )
}
