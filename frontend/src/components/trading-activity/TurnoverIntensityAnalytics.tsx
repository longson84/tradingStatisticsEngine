import type { InstrumentTradeStatisticsResponse } from "@/lib/api"
import { fmtDate, fmtPct } from "@/lib/format"


type Analysis = InstrumentTradeStatisticsResponse["turnover_intensity"]
type Point = Analysis["points"][number]
type UnavailableReason = NonNullable<Point["unavailable_reason"]>

const REASON_COPY: Record<UnavailableReason, string> = {
  invalid_total_value: "Total traded value is invalid",
  invalid_market_cap: "Market capitalization is invalid",
  non_positive_market_cap: "Market capitalization is zero or negative",
  insufficient_history: "Fewer than 20 prior stored sessions",
  invalid_baseline_window: "The prior 20-session window contains unavailable data",
  zero_baseline_variance: "Prior 20-session window has no variation",
}

export function TurnoverIntensityAnalytics({ analysis }: { analysis: Analysis }) {
  const latestIntensity = findLatest(analysis.points, point => point.intensity != null)
  const latestAnomaly = findLatest(analysis.points, point => point.anomaly_score != null)
  const reasons = [...new Set(
    analysis.points.flatMap(point => point.unavailable_reason ? [point.unavailable_reason] : []),
  )]

  return <section className="mb-5 rounded-xl border border-border bg-card p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="font-semibold">Turnover intensity analytics</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Daily traded value ÷ market capitalization. The anomaly compares each session with its prior {analysis.baseline_sessions} stored sessions; the current session is excluded from its baseline.
        </p>
      </div>
      <span className="rounded-md border border-border px-2 py-1 text-[10px] text-muted-foreground">
        {analysis.formula_version}
      </span>
    </div>

    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      <MetricCard
        label="Latest intensity"
        date={latestIntensity?.trading_date}
        value={latestIntensity?.intensity == null ? "Not available" : fmtPct(latestIntensity.intensity * 100)}
      />
      <MetricCard
        label="Latest anomaly"
        date={latestAnomaly?.trading_date}
        value={latestAnomaly?.anomaly_score == null ? "Not available" : formatAnomaly(latestAnomaly.anomaly_score)}
      />
    </div>

    <IntensityChart points={analysis.points} baselineSessions={analysis.baseline_sessions} />
    <AnomalyChart points={analysis.points} />

    {reasons.length > 0 && <div className="mt-4 rounded-md border border-border bg-muted/20 p-3 text-xs">
      <div className="font-medium">Not available on some sessions</div>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
        {reasons.map(reason => <li key={reason}>{REASON_COPY[reason]}</li>)}
      </ul>
    </div>}
    <p className="mt-3 text-[11px] text-muted-foreground">
      Calculated from stored activity only. Missing stored sessions are not inferred, and these display values are not same-session strategy inputs.
    </p>
  </section>
}

function MetricCard({ label, date, value }: { label: string; date?: string; value: string }) {
  return <div className="rounded-lg border border-border bg-background p-4">
    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
      {label}{date ? ` · ${fmtDate(date)}` : ""}
    </div>
    <div className="mt-1 text-lg font-semibold tabular-nums">{value}</div>
  </div>
}

function IntensityChart({ points, baselineSessions }: { points: Point[]; baselineSessions: number }) {
  const values = points.flatMap(point => [point.intensity, point.baseline]).filter(isNumber)
  const high = Math.max(...values, 0.01)
  const width = chartWidth(points.length)
  const plot = chartGeometry(width, points.length)
  const y = (value: number) => plot.top + (1 - value / high) * plot.height

  return <ChartFrame title={`Turnover intensity and prior ${baselineSessions}-session baseline`} width={width}>
    <line x1={plot.left} x2={plot.right} y1={y(0)} y2={y(0)} stroke="currentColor" opacity={0.25} />
    <text x={plot.left - 8} y={y(high) + 4} textAnchor="end" fill="currentColor" fontSize={10}>{fmtPct(high * 100)}</text>
    <text x={plot.left - 8} y={y(0) + 4} textAnchor="end" fill="currentColor" fontSize={10}>0%</text>
    <SeriesSegments points={points} value={point => point.intensity} x={plot.x} y={y} color="#2563eb" />
    <SeriesSegments points={points} value={point => point.baseline} x={plot.x} y={y} color="#d97706" />
    <SeriesPoints points={points} value={point => point.intensity} x={plot.x} y={y} color="#2563eb" series="intensity" />
    <SeriesPoints points={points} value={point => point.baseline} x={plot.x} y={y} color="#d97706" series="baseline" />
    {points.map((point, index) => <PointTitle key={point.trading_date} point={point} x={plot.x(index)} />)}
    <ChartDates points={points} x={plot.x} />
    <text x={plot.left} y={18} fill="#2563eb" fontSize={10}>Intensity</text>
    <text x={plot.left + 58} y={18} fill="#d97706" fontSize={10}>Prior baseline</text>
  </ChartFrame>
}

function AnomalyChart({ points }: { points: Point[] }) {
  const values = points.map(point => point.anomaly_score).filter(isNumber)
  const bound = Math.max(...values.map(Math.abs), 1)
  const width = chartWidth(points.length)
  const plot = chartGeometry(width, points.length)
  const y = (value: number) => plot.top + (bound - value) / (bound * 2) * plot.height
  const zero = y(0)

  return <ChartFrame title="Turnover intensity anomaly score" width={width}>
    <line x1={plot.left} x2={plot.right} y1={zero} y2={zero} stroke="currentColor" opacity={0.35} />
    <text x={plot.left - 8} y={y(bound) + 4} textAnchor="end" fill="currentColor" fontSize={10}>+{bound.toFixed(1)}σ</text>
    <text x={plot.left - 8} y={zero + 4} textAnchor="end" fill="currentColor" fontSize={10}>0σ</text>
    <text x={plot.left - 8} y={y(-bound) + 4} textAnchor="end" fill="currentColor" fontSize={10}>−{bound.toFixed(1)}σ</text>
    {points.map((point, index) => point.anomaly_score == null ? null : <g key={point.trading_date}>
      <title>{`${fmtDate(point.trading_date)}: ${formatAnomaly(point.anomaly_score)}`}</title>
      <rect
        x={plot.x(index) - Math.max(1, plot.step - 6) / 2}
        y={Math.min(zero, y(point.anomaly_score))}
        width={Math.max(1, plot.step - 6)}
        height={Math.max(1, Math.abs(y(point.anomaly_score) - zero))}
        fill={point.anomaly_score >= 0 ? "#16a34a" : "#dc2626"}
      />
    </g>)}
    <ChartDates points={points} x={plot.x} />
  </ChartFrame>
}

function ChartFrame({ title, width, children }: { title: string; width: number; children: React.ReactNode }) {
  return <div className="mt-5">
    <h3 className="text-sm font-medium">{title}</h3>
    <div className="mt-2 overflow-x-auto">
      <svg role="img" aria-label={title} width={width} height={270} className="text-muted-foreground">
        <title>{title}</title>
        {children}
      </svg>
    </div>
  </div>
}

function SeriesSegments({
  points,
  value,
  x,
  y,
  color,
}: {
  points: Point[]
  value: (point: Point) => number | null
  x: (index: number) => number
  y: (value: number) => number
  color: string
}) {
  return <>{points.slice(1).map((point, index) => {
    const previous = value(points[index])
    const current = value(point)
    if (previous == null || current == null) return null
    return <line
      key={`${point.trading_date}-${color}`}
      x1={x(index)} y1={y(previous)} x2={x(index + 1)} y2={y(current)}
      stroke={color} strokeWidth={2}
    />
  })}</>
}

function SeriesPoints({
  points,
  value,
  x,
  y,
  color,
  series,
}: {
  points: Point[]
  value: (point: Point) => number | null
  x: (index: number) => number
  y: (value: number) => number
  color: string
  series: "intensity" | "baseline"
}) {
  return <>{points.map((point, index) => {
    const current = value(point)
    if (current == null) return null
    return <circle
      key={`${point.trading_date}-${series}`}
      data-series={series}
      cx={x(index)} cy={y(current)} r={3}
      fill={color}
    />
  })}</>
}

function PointTitle({ point, x }: { point: Point; x: number }) {
  const reason = point.unavailable_reason ? REASON_COPY[point.unavailable_reason] : null
  const intensity = point.intensity == null ? "intensity Not available" : `intensity ${fmtPct(point.intensity * 100)}`
  const baseline = point.baseline == null ? "" : `, baseline ${fmtPct(point.baseline * 100)}`
  const anomaly = point.anomaly_score == null
    ? `, anomaly Not available${reason ? ` — ${reason}` : ""}`
    : `, anomaly ${formatAnomaly(point.anomaly_score)}`
  return <circle cx={x} cy={245} r={6} fill="transparent">
    <title>{`${fmtDate(point.trading_date)}: ${intensity}${baseline}${anomaly}`}</title>
  </circle>
}

function ChartDates({ points, x }: { points: Point[]; x: (index: number) => number }) {
  const every = Math.max(1, Math.ceil(points.length / 8))
  return <>{points.map((point, index) => index % every === 0
    ? <text key={point.trading_date} x={x(index)} y={260} textAnchor="middle" fill="currentColor" fontSize={10}>{fmtDate(point.trading_date)}</text>
    : null)}</>
}

function chartWidth(pointCount: number): number {
  return Math.max(720, pointCount * 28 + 90)
}

function chartGeometry(width: number, pointCount: number) {
  const left = 74
  const right = width - 18
  const top = 28
  const height = 205
  const step = pointCount > 1 ? (right - left) / (pointCount - 1) : 0
  return { left, right, top, height, step, x: (index: number) => left + index * step }
}

function findLatest(points: Point[], predicate: (point: Point) => boolean): Point | undefined {
  return [...points].reverse().find(predicate)
}

function isNumber(value: number | null): value is number {
  return value != null
}

function formatAnomaly(value: number): string {
  return `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value).toFixed(2)}σ`
}
