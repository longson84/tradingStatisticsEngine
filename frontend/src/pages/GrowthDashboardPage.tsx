import { useState, type ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"
import { ChevronDown, ChevronRight, RefreshCw, Sparkles } from "lucide-react"
import { Sidebar } from "@/components/Sidebar"
import {
  growthAssessmentApi,
  growthAnalysisApi,
  type AnnualGrowthRow,
  type GrowthAnalysisResponse,
  type GrowthMetricSnapshot,
  type QuarterlyGrowthRow,
  type QuarterlyGrowthSnapshot,
} from "@/lib/api"
import { fmtDate, fmtInt, fmtNum, fmtPct } from "@/lib/format"

function Label({ children }: { children: ReactNode }) {
  return (
    <span className="block text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-1">
      {children}
    </span>
  )
}

function NumberInput({
  value,
  onChange,
  min,
  max,
}: {
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
}) {
  return (
    <input
      type="number"
      value={value}
      min={min}
      max={max}
      onChange={e => onChange(Number(e.target.value))}
      className="w-full bg-background border border-input rounded px-2 py-1.5 text-sm text-foreground focus:outline-none focus:border-ring"
    />
  )
}

export function GrowthDashboardPage() {
  const [symbol, setSymbol] = useState("MSFT")
  const [currentYear, setCurrentYear] = useState(new Date().getFullYear() - 1)
  const [years, setYears] = useState(20)
  const [runId, setRunId] = useState(0)
  const [params, setParams] = useState<Parameters<typeof growthAnalysisApi>[0] | null>(null)

  const { data, isFetching, error } = useQuery({
    queryKey: ["growth-dashboard", params, runId],
    queryFn: () => growthAnalysisApi(params!),
    enabled: params != null,
    retry: false,
  })

  const controls = (
    <div className="space-y-4">
      <div>
        <Label>Symbol</Label>
        <input
          value={symbol}
          onChange={e => setSymbol(e.target.value.toUpperCase())}
          className="w-full bg-background border border-input rounded px-2 py-1.5 text-sm text-foreground uppercase focus:outline-none focus:border-ring"
        />
      </div>

      <div>
        <Label>Current Year</Label>
        <NumberInput value={currentYear} onChange={setCurrentYear} min={1990} max={2100} />
      </div>

      <div>
        <Label>Lookback Years</Label>
        <NumberInput value={years} onChange={setYears} min={1} max={40} />
      </div>

      <button
        onClick={() => {
          setParams({ symbol, current_year: currentYear, years })
          setRunId(id => id + 1)
        }}
        disabled={isFetching || !symbol.trim()}
        className="w-full py-2.5 rounded-md bg-primary hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed text-primary-foreground text-sm font-semibold transition-colors tracking-wide"
      >
        {isFetching ? "Loading..." : "Analyse"}
      </button>
    </div>
  )

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar className="w-72" children={controls} />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="flex items-end justify-between gap-4 pb-4 border-b border-border">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Growth Dashboard</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Revenue, profit, cash-flow, EPS, margin, and share-count growth.
            </p>
          </div>
          {data && (
            <div className="text-xs text-muted-foreground text-right">
              <div>{data.entity_name}</div>
              <div>CIK {data.cik}</div>
            </div>
          )}
        </div>

        {isFetching && <LoadingBar />}

        {error && !isFetching && (
          <div className="mt-4 rounded-lg border border-red-500/30 bg-red-950/20 px-4 py-3 text-sm text-red-300">
            {(error as Error).message}
          </div>
        )}

        {!data && !isFetching && !error && (
          <div className="flex h-64 items-center justify-center text-sm text-muted-foreground/50">
            Enter a ticker and current year to load growth metrics.
          </div>
        )}

        {data && !isFetching && (
          <div className="mt-5 space-y-6">
            <HeaderStrip data={data} />
            <GrowthQualityCards data={data} />
            <AssessmentSection data={data} />
            <GrowthMetricTable rows={data.annual_metrics} />
            <QuarterlyMomentumTable rows={data.quarterly_metrics} />
            <GrowthVisuals data={data} />
            <AnnualGrowthHistory rows={data.annual_rows} />
            <QuarterGrowthHistory rows={data.quarterly_rows} />
          </div>
        )}
      </main>
    </div>
  )
}

function AssessmentSection({ data }: { data: GrowthAnalysisResponse }) {
  const {
    data: assessment,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ["growth-assessment", data.symbol, data.requested_current_year, data.first_year, data.last_year],
    queryFn: () => growthAssessmentApi(data),
    enabled: false,
    retry: false,
  })

  return (
    <section>
      <div className="flex items-center justify-between gap-3 mb-2">
        <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Assessment From Numbers</h2>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-semibold hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isFetching ? <RefreshCw size={14} className="animate-spin" /> : <Sparkles size={14} />}
          {assessment ? "Refresh" : "Generate"}
        </button>
      </div>
      <div className="border border-border rounded-lg bg-card overflow-hidden">
        {error && (
          <div className="border-b border-red-500/20 bg-red-500/8 px-4 py-3 text-sm text-red-700 dark:text-red-300">
            {(error as Error).message}
          </div>
        )}
        {assessment ? (
          <>
            <div className="grid grid-cols-1 xl:grid-cols-5 divide-y xl:divide-y-0 xl:divide-x divide-border">
              <AssessmentColumn title="Good Things" items={assessment.good_things} tone="good" />
              <AssessmentColumn title="Bad Things" items={assessment.bad_things} tone="bad" />
              <AssessmentColumn title="Risks" items={assessment.risks} tone="risk" />
              <AssessmentColumn title="Opportunities" items={assessment.opportunities} tone="opportunity" />
              <AssessmentColumn title="Investment Considerations" items={assessment.investment_considerations} tone="focus" />
            </div>
            <div className="border-t border-border px-4 py-2 text-[11px] text-muted-foreground flex items-center justify-between gap-4">
              <span>{assessment.disclaimer}</span>
              <span className="shrink-0 tabular-nums">{assessment.model}</span>
            </div>
            <PromptCopySection prompt={assessment.prompt} />
          </>
        ) : (
          <div className="px-4 py-8 text-sm text-muted-foreground">
            {isFetching ? "Generating assessment..." : "No assessment generated."}
          </div>
        )}
      </div>
    </section>
  )
}

function PromptCopySection({ prompt }: { prompt: string }) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  async function copyPrompt() {
    await navigator.clipboard?.writeText(prompt)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div className="border-t border-border">
      <div className="flex items-center justify-between gap-3 px-4 py-2 border-b border-border bg-muted/30">
        <button
          onClick={() => setOpen(value => !value)}
          className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground hover:text-foreground"
        >
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          Prompt
        </button>
        <button
          onClick={copyPrompt}
          className="rounded border border-border bg-card px-2 py-1 text-[11px] font-semibold hover:bg-accent"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {open && (
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap px-4 py-3 text-xs leading-relaxed text-muted-foreground">
          {prompt}
        </pre>
      )}
    </div>
  )
}

function AssessmentColumn({
  title,
  items,
  tone,
}: {
  title: string
  items: string[]
  tone: "good" | "bad" | "risk" | "opportunity" | "focus"
}) {
  const color =
    tone === "good"
      ? "text-emerald-700 dark:text-emerald-300"
      : tone === "bad"
        ? "text-rose-700 dark:text-rose-300"
        : tone === "risk"
          ? "text-amber-700 dark:text-amber-300"
          : tone === "opportunity"
            ? "text-teal-700 dark:text-teal-300"
          : "text-sky-700 dark:text-sky-300"

  return (
    <div className="p-4">
      <div className={`text-xs font-semibold uppercase tracking-wide ${color}`}>{title}</div>
      <ul className="mt-3 space-y-2">
        {items.length ? items.map((item, index) => (
          <li key={index} className="grid grid-cols-[16px_1fr] gap-2 text-sm leading-relaxed">
            <span className={`mt-2 h-1.5 w-1.5 rounded-full ${dotColor(tone)}`} />
            <span>{item}</span>
          </li>
        )) : (
          <li className="text-sm text-muted-foreground">n/a</li>
        )}
      </ul>
    </div>
  )
}

function dotColor(tone: "good" | "bad" | "risk" | "opportunity" | "focus") {
  if (tone === "good") return "bg-emerald-500"
  if (tone === "bad") return "bg-rose-500"
  if (tone === "risk") return "bg-amber-500"
  if (tone === "opportunity") return "bg-teal-500"
  return "bg-sky-500"
}

function HeaderStrip({ data }: { data: GrowthAnalysisResponse }) {
  const cells = [
    ["Symbol", data.symbol],
    ["Years", `${data.first_year ?? "n/a"} - ${data.last_year ?? "n/a"}`],
    ["Annual Rows", fmtInt(data.annual_rows.length)],
    ["Quarter Rows", fmtInt(data.quarterly_rows.length)],
  ]
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-px border border-border rounded-lg overflow-hidden bg-border max-w-4xl">
      {cells.map(([label, value]) => (
        <div key={label} className="bg-card px-3 py-3">
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
          <div className="mt-1 text-sm font-semibold tabular-nums">{value}</div>
        </div>
      ))}
    </div>
  )
}

function GrowthQualityCards({ data }: { data: GrowthAnalysisResponse }) {
  const s = data.summary
  const cards = [
    ["Revenue 5Y CAGR", s.revenue_cagr_5y_pct, "pct"],
    ["Op Income 5Y CAGR", s.operating_income_cagr_5y_pct, "pct"],
    ["FCF 5Y CAGR", s.free_cash_flow_cagr_5y_pct, "pct"],
    ["EPS 5Y CAGR", s.eps_cagr_5y_pct, "pct"],
    ["Op Margin", s.latest_operating_margin_pct, "pct"],
    ["FCF Margin", s.latest_fcf_margin_pct, "pct"],
    ["Op Margin 5Y Chg", s.operating_margin_change_5y_pct, "pp"],
    ["FCF Margin 5Y Chg", s.fcf_margin_change_5y_pct, "pp"],
    ["Shares 5Y Chg", s.share_count_change_5y_pct, "inversePct"],
  ] as const
  return (
    <section>
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Growth Quality</h2>
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        {cards.map(([label, value, kind]) => (
          <div key={label} className="border border-border rounded-lg bg-card px-3 py-3">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
            <div className={metricValueClass(value, kind)}>
              {kind === "pp" ? formatPp(value) : formatPctLike(value)}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function GrowthMetricTable({ rows }: { rows: GrowthMetricSnapshot[] }) {
  return (
    <section>
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Annual Growth Stack</h2>
      <div className="border border-border rounded-lg overflow-hidden bg-card">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="text-left px-3 py-2 font-medium">Metric</th>
              <th className="text-right px-3 py-2 font-medium">Latest</th>
              <th className="text-right px-3 py-2 font-medium">Latest YoY</th>
              <th className="text-right px-3 py-2 font-medium">3Y CAGR</th>
              <th className="text-right px-3 py-2 font-medium">5Y CAGR</th>
              <th className="text-right px-3 py-2 font-medium">10Y CAGR</th>
              <th className="text-right px-3 py-2 font-medium">Margin</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map(row => (
              <tr key={row.metric} className="hover:bg-muted/30">
                <td className="px-3 py-2 font-semibold">{row.metric}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatMetricValue(row.metric, row.latest_value)}</td>
                <PctCell value={row.latest_yoy_pct} />
                <PctCell value={row.cagr_3y_pct} />
                <PctCell value={row.cagr_5y_pct} />
                <PctCell value={row.cagr_10y_pct} />
                <PctCell value={row.latest_margin_pct} neutral />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function QuarterlyMomentumTable({ rows }: { rows: QuarterlyGrowthSnapshot[] }) {
  return (
    <section>
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Quarterly Momentum</h2>
      <div className="border border-border rounded-lg overflow-hidden bg-card">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="text-left px-3 py-2 font-medium">Metric</th>
              <th className="text-right px-3 py-2 font-medium">Latest</th>
              <th className="text-right px-3 py-2 font-medium">Latest YoY</th>
              <th className="text-right px-3 py-2 font-medium">Prior YoY</th>
              <th className="text-right px-3 py-2 font-medium">4Q Avg YoY</th>
              <th className="text-right px-3 py-2 font-medium">Latest QoQ</th>
              <th className="text-right px-3 py-2 font-medium">Direction</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map(row => (
              <tr key={row.metric} className="hover:bg-muted/30">
                <td className="px-3 py-2 font-semibold">{row.metric}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatMetricValue(row.metric, row.latest_value)}</td>
                <PctCell value={row.latest_yoy_pct} />
                <PctCell value={row.previous_yoy_pct} />
                <PctCell value={row.average_4q_yoy_pct} />
                <PctCell value={row.latest_qoq_pct} />
                <td className="px-3 py-2 text-right">
                  <DirectionBadge value={row.direction} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function GrowthVisuals({ data }: { data: GrowthAnalysisResponse }) {
  const annual = [
    { label: "Revenue YoY", points: data.annual_rows.map(row => ({ label: String(row.fiscal_year), value: row.revenue_yoy_pct })) },
    { label: "Gross Profit YoY", points: data.annual_rows.map(row => ({ label: String(row.fiscal_year), value: row.gross_profit_yoy_pct })) },
    { label: "Op Income YoY", points: data.annual_rows.map(row => ({ label: String(row.fiscal_year), value: row.operating_income_yoy_pct })) },
    { label: "FCF YoY", points: data.annual_rows.map(row => ({ label: String(row.fiscal_year), value: row.free_cash_flow_yoy_pct })) },
    { label: "EPS YoY", points: data.annual_rows.map(row => ({ label: String(row.fiscal_year), value: row.eps_yoy_pct })) },
  ]
  const quarterly = [
    { label: "Revenue YoY", points: data.quarterly_rows.map(row => ({ label: quarterLabel(row.period_end), value: row.revenue_yoy_pct })) },
    { label: "Revenue QoQ", points: data.quarterly_rows.map(row => ({ label: quarterLabel(row.period_end), value: row.revenue_qoq_pct })) },
    { label: "Op Income YoY", points: data.quarterly_rows.map(row => ({ label: quarterLabel(row.period_end), value: row.operating_income_yoy_pct })) },
    { label: "FCF YoY", points: data.quarterly_rows.map(row => ({ label: quarterLabel(row.period_end), value: row.free_cash_flow_yoy_pct })) },
    { label: "EPS YoY", points: data.quarterly_rows.map(row => ({ label: quarterLabel(row.period_end), value: row.eps_yoy_pct })) },
  ]
  return (
    <section>
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Growth Visuals</h2>
      <div className="space-y-4">
        <GrowthBarGroup title="Annual" series={annual} />
        <GrowthBarGroup title="Quarterly" series={quarterly} />
      </div>
    </section>
  )
}

function GrowthBarGroup({
  title,
  series,
}: {
  title: string
  series: Array<{ label: string; points: Array<{ label: string; value: number | null }> }>
}) {
  return (
    <div className="border border-border rounded-lg bg-card overflow-hidden">
      <div className="px-4 py-2 border-b border-border text-sm font-semibold">{title}</div>
      <div className="grid grid-cols-1 lg:grid-cols-5 divide-y lg:divide-y-0 lg:divide-x divide-border">
        {series.map(item => (
          <GrowthBars key={item.label} label={item.label} points={item.points} />
        ))}
      </div>
    </div>
  )
}

function GrowthBars({ label, points }: { label: string; points: Array<{ label: string; value: number | null }> }) {
  const values = points
    .map(point => point.value)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value))
  const maxAbs = Math.max(5, ...values.map(value => Math.abs(value)))
  const latest = [...points].reverse().find(point => point.value != null)
  return (
    <div className="px-3 py-3">
      <div className="flex items-start justify-between gap-2">
        <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
        <div className={metricValueClass(latest?.value, "pct")}>{formatPctLike(latest?.value)}</div>
      </div>
      <div className="relative mt-3 h-24 rounded bg-muted/70 overflow-hidden">
        <div className="absolute left-0 right-0 top-1/2 h-px bg-border" />
        <div className="absolute inset-x-2 inset-y-2 flex items-stretch gap-1">
          {points.map(point => {
            const value = point.value
            const height = value == null ? 2 : Math.max(3, Math.abs(value) / maxAbs * 42)
            return (
              <div key={point.label} className="relative flex-1" title={`${point.label}: ${formatPctLike(value)}`}>
                <div
                  className={[
                    "absolute left-0 right-0 rounded-sm",
                    value == null ? "bg-muted-foreground/25" : value < 0 ? "bg-rose-500/60" : "bg-emerald-500/60",
                  ].join(" ")}
                  style={value == null || value >= 0
                    ? { height: `${height}px`, bottom: "50%" }
                    : { height: `${height}px`, top: "50%" }}
                />
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function AnnualGrowthHistory({ rows }: { rows: AnnualGrowthRow[] }) {
  return (
    <section>
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Annual Growth History</h2>
      <div className="border border-border rounded-lg overflow-x-auto bg-card">
        <table className="w-full min-w-[980px] text-sm">
          <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="text-right px-3 py-2 font-medium">Year</th>
              <th className="text-right px-3 py-2 font-medium">Revenue</th>
              <th className="text-right px-3 py-2 font-medium">Revenue YoY</th>
              <th className="text-right px-3 py-2 font-medium">Gross Profit YoY</th>
              <th className="text-right px-3 py-2 font-medium">Op Income YoY</th>
              <th className="text-right px-3 py-2 font-medium">Net Income YoY</th>
              <th className="text-right px-3 py-2 font-medium">FCF YoY</th>
              <th className="text-right px-3 py-2 font-medium">EPS YoY</th>
              <th className="text-right px-3 py-2 font-medium">Shares YoY</th>
              <th className="text-right px-3 py-2 font-medium">Op Margin</th>
              <th className="text-right px-3 py-2 font-medium">FCF Margin</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.slice().reverse().map(row => (
              <tr key={row.fiscal_year} className="hover:bg-muted/30">
                <td className="px-3 py-2 text-right tabular-nums font-medium">{row.fiscal_year}</td>
                <MoneyCell value={row.revenue} />
                <PctCell value={row.revenue_yoy_pct} />
                <PctCell value={row.gross_profit_yoy_pct} />
                <PctCell value={row.operating_income_yoy_pct} />
                <PctCell value={row.net_income_yoy_pct} />
                <PctCell value={row.free_cash_flow_yoy_pct} />
                <PctCell value={row.eps_yoy_pct} />
                <PctCell value={row.share_count_yoy_pct} inverse />
                <PctCell value={row.operating_margin_pct} neutral />
                <PctCell value={row.free_cash_flow_margin_pct} neutral />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function QuarterGrowthHistory({ rows }: { rows: QuarterlyGrowthRow[] }) {
  return (
    <section>
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Quarter Growth History</h2>
      <div className="border border-border rounded-lg overflow-x-auto bg-card">
        <table className="w-full min-w-[900px] text-sm">
          <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="text-right px-3 py-2 font-medium">Quarter</th>
              <th className="text-right px-3 py-2 font-medium">Period End</th>
              <th className="text-right px-3 py-2 font-medium">Revenue</th>
              <th className="text-right px-3 py-2 font-medium">Revenue YoY</th>
              <th className="text-right px-3 py-2 font-medium">Revenue QoQ</th>
              <th className="text-right px-3 py-2 font-medium">Op Income YoY</th>
              <th className="text-right px-3 py-2 font-medium">Net Income YoY</th>
              <th className="text-right px-3 py-2 font-medium">FCF YoY</th>
              <th className="text-right px-3 py-2 font-medium">EPS YoY</th>
              <th className="text-right px-3 py-2 font-medium">Op Margin</th>
              <th className="text-right px-3 py-2 font-medium">FCF Margin</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.slice().reverse().map(row => (
              <tr key={row.period_end} className="hover:bg-muted/30">
                <td className="px-3 py-2 text-right tabular-nums font-medium">{quarterLabel(row.period_end)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmtDate(row.period_end)}</td>
                <MoneyCell value={row.revenue} />
                <PctCell value={row.revenue_yoy_pct} />
                <PctCell value={row.revenue_qoq_pct} />
                <PctCell value={row.operating_income_yoy_pct} />
                <PctCell value={row.net_income_yoy_pct} />
                <PctCell value={row.free_cash_flow_yoy_pct} />
                <PctCell value={row.eps_yoy_pct} />
                <PctCell value={row.operating_margin_pct} neutral />
                <PctCell value={row.free_cash_flow_margin_pct} neutral />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function DirectionBadge({ value }: { value: string | null }) {
  if (!value) {
    return <span className="text-muted-foreground">n/a</span>
  }
  const positive = value === "accelerating"
  const negative = value === "decelerating"
  return (
    <span className={[
      "inline-block min-w-24 rounded px-2 py-1 text-center text-xs font-semibold capitalize",
      positive ? "bg-emerald-500/14 text-emerald-700 dark:text-emerald-300" : "",
      negative ? "bg-rose-500/14 text-rose-700 dark:text-rose-300" : "",
      !positive && !negative ? "bg-muted text-muted-foreground" : "",
    ].join(" ")}>
      {value}
    </span>
  )
}

function MoneyCell({ value }: { value: number | null }) {
  return (
    <td className="px-3 py-2 text-right tabular-nums">
      {value != null ? fmtNum(value / 1e9, 1) + "B" : "n/a"}
    </td>
  )
}

function PctCell({
  value,
  neutral = false,
  inverse = false,
}: {
  value: number | null
  neutral?: boolean
  inverse?: boolean
}) {
  return (
    <td className="px-3 py-2 text-right tabular-nums">
      {value == null ? "n/a" : (
        <span className={[
          "inline-block min-w-16 rounded px-2 py-1",
          !neutral && !inverse && value < 0 ? "bg-rose-500/14 text-rose-700 dark:text-rose-300" : "",
          !neutral && !inverse && value > 0 ? "bg-emerald-500/14 text-emerald-700 dark:text-emerald-300" : "",
          inverse && value < 0 ? "bg-emerald-500/14 text-emerald-700 dark:text-emerald-300" : "",
          inverse && value > 0 ? "bg-rose-500/14 text-rose-700 dark:text-rose-300" : "",
        ].join(" ")}>
          {fmtPct(value)}
        </span>
      )}
    </td>
  )
}

function metricValueClass(value: number | null | undefined, kind: "pct" | "inversePct" | "pp") {
  const base = "mt-1 text-lg font-semibold tabular-nums"
  if (value == null) return base
  if (kind === "inversePct") {
    if (value < 0) return `${base} text-emerald-700 dark:text-emerald-300`
    if (value > 0) return `${base} text-rose-600 dark:text-rose-300`
    return base
  }
  if (value < 0) return `${base} text-rose-600 dark:text-rose-300`
  if (value > 0) return `${base} text-emerald-700 dark:text-emerald-300`
  return base
}

function formatMetricValue(metric: string, value: number | null) {
  if (value == null) return "n/a"
  if (metric.includes("EPS")) return fmtNum(value, 2)
  return fmtNum(value / 1e9, 1) + "B"
}

function formatPctLike(value: number | null | undefined) {
  return value == null ? "n/a" : fmtPct(value)
}

function formatPp(value: number | null | undefined) {
  return value == null ? "n/a" : `${fmtNum(value, 2)} pp`
}

function quarterLabel(periodEnd: string) {
  const [year, month] = periodEnd.split("-").map(Number)
  if (!year || !month) return periodEnd
  return `${year} Q${Math.floor((month - 1) / 3) + 1}`
}

function LoadingBar() {
  return (
    <div className="mt-4 h-0.5 w-full bg-border rounded overflow-hidden relative">
      <div
        className="absolute h-full w-1/3 bg-primary rounded"
        style={{ animation: "progress-slide 1.2s ease-in-out infinite" }}
      />
    </div>
  )
}
