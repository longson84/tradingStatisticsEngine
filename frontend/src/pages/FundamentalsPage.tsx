import { useState, type ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"
import { Sidebar } from "@/components/Sidebar"
import { fundamentalsSecApi, type FundamentalResponse, type FundamentalQuarterRow, type FundamentalRow } from "@/lib/api"
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

export function FundamentalsPage() {
  const [symbol, setSymbol] = useState("MSFT")
  const [currentYear, setCurrentYear] = useState(new Date().getFullYear() - 1)
  const [years, setYears] = useState(20)
  const [runId, setRunId] = useState(0)
  const [params, setParams] = useState<Parameters<typeof fundamentalsSecApi>[0] | null>(null)

  const { data, isFetching, error } = useQuery({
    queryKey: ["fundamentals-sec", params, runId],
    queryFn: () => fundamentalsSecApi(params!),
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
            <h1 className="text-2xl font-bold tracking-tight">Fundamentals</h1>
            <p className="text-sm text-muted-foreground mt-1">
              SEC annual and quarterly fundamentals, built from company facts.
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
            Enter a ticker and current year to load SEC fundamentals.
          </div>
        )}

        {data && !isFetching && (
          <div className="mt-5 space-y-6">
            <HeaderStrip data={data} />
            <SummaryCards data={data} />
            <GrowthVisualGrid data={data} />
            <AnnualGrowthTable rows={data.rows} />
            <MetricTrendGrid rows={data.rows} />
            <FundamentalTable rows={data.rows} />
            <QuarterGrowthTable rows={data.quarter_rows} />
            <QuarterFundamentalTable rows={data.quarter_rows} />
          </div>
        )}
      </main>
    </div>
  )
}

function HeaderStrip({ data }: { data: FundamentalResponse }) {
  const cells = [
    ["Symbol", data.symbol],
    ["Years", `${data.first_year ?? "n/a"} - ${data.last_year ?? "n/a"}`],
    ["Rows", fmtInt(data.rows.length)],
    ["Requested Year", fmtInt(data.requested_current_year)],
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

function SummaryCards({ data }: { data: FundamentalResponse }) {
  const s = data.summary
  const cards = [
    ["Revenue CAGR", s.revenue_cagr_pct, "pct"],
    ["Op Income CAGR", s.operating_income_cagr_pct, "pct"],
    ["Net Income CAGR", s.net_income_cagr_pct, "pct"],
    ["FCF CAGR", s.free_cash_flow_cagr_pct, "pct"],
    ["EPS CAGR", s.eps_cagr_pct, "pct"],
    ["Latest Op Margin", s.latest_operating_margin_pct, "pct"],
    ["Latest FCF Margin", s.latest_fcf_margin_pct, "pct"],
    ["Capex / Revenue", s.latest_capex_to_revenue_pct, "pct"],
    ["Debt / FCF", s.latest_debt_to_fcf, "num"],
    ["Net Cash", s.latest_net_cash, "money"],
    ["Share Count Chg", s.share_count_change_pct, "pct"],
  ] as const
  return (
    <section>
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Quality Snapshot</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-3">
        {cards.map(([label, value, kind]) => (
          <div key={label} className="border border-border rounded-lg bg-card px-3 py-3">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
            <div className={[
              "mt-1 text-lg font-semibold tabular-nums",
              value != null && kind === "pct" && value < 0 ? "text-rose-600 dark:text-rose-300" : "",
              value != null && kind === "pct" && value > 0 ? "text-emerald-700 dark:text-emerald-300" : "",
            ].join(" ")}>
              {formatValue(value, kind)}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function GrowthVisualGrid({ data }: { data: FundamentalResponse }) {
  const annualSeries = [
    { label: "Revenue YoY", points: data.rows.map(row => ({ label: String(row.fiscal_year), value: row.revenue_yoy_pct })) },
    { label: "Op Income YoY", points: data.rows.map(row => ({ label: String(row.fiscal_year), value: row.operating_income_yoy_pct })) },
    { label: "Net Income YoY", points: data.rows.map(row => ({ label: String(row.fiscal_year), value: row.net_income_yoy_pct })) },
    { label: "FCF YoY", points: data.rows.map(row => ({ label: String(row.fiscal_year), value: row.free_cash_flow_yoy_pct })) },
    { label: "EPS YoY", points: data.rows.map(row => ({ label: String(row.fiscal_year), value: row.eps_yoy_pct })) },
  ]
  const quarterSeries = [
    { label: "Revenue YoY", points: data.quarter_rows.map(row => ({ label: formatQuarterLabel(row.period_end), value: row.revenue_yoy_pct })) },
    { label: "Revenue QoQ", points: data.quarter_rows.map(row => ({ label: formatQuarterLabel(row.period_end), value: row.revenue_qoq_pct })) },
    { label: "Op Income YoY", points: data.quarter_rows.map(row => ({ label: formatQuarterLabel(row.period_end), value: row.operating_income_yoy_pct })) },
    { label: "Net Income YoY", points: data.quarter_rows.map(row => ({ label: formatQuarterLabel(row.period_end), value: row.net_income_yoy_pct })) },
    { label: "FCF YoY", points: data.quarter_rows.map(row => ({ label: formatQuarterLabel(row.period_end), value: row.free_cash_flow_yoy_pct })) },
  ]
  return (
    <section>
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Growth Visuals</h2>
      <div className="grid grid-cols-1 2xl:grid-cols-2 gap-4">
        <GrowthSeriesGroup title="Annual Growth" series={annualSeries} />
        <GrowthSeriesGroup title="Quarter Growth" series={quarterSeries} />
      </div>
    </section>
  )
}

function GrowthSeriesGroup({
  title,
  series,
}: {
  title: string
  series: Array<{ label: string; points: Array<{ label: string; value: number | null }> }>
}) {
  return (
    <div className="border border-border rounded-lg bg-card overflow-hidden">
      <div className="px-4 py-2 border-b border-border">
        <div className="text-sm font-semibold">{title}</div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-5 divide-y md:divide-y-0 md:divide-x divide-border">
        {series.map(item => (
          <GrowthSparkCard key={item.label} label={item.label} points={item.points} />
        ))}
      </div>
    </div>
  )
}

function GrowthSparkCard({
  label,
  points,
}: {
  label: string
  points: Array<{ label: string; value: number | null }>
}) {
  const values = points
    .map(point => point.value)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value))
  const maxAbs = Math.max(5, ...values.map(value => Math.abs(value)))
  const latest = [...points].reverse().find(point => point.value != null)
  return (
    <div className="px-3 py-3">
      <div className="flex items-start justify-between gap-2">
        <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
        <div className={[
          "text-xs font-semibold tabular-nums",
          latest?.value != null && latest.value < 0 ? "text-rose-600 dark:text-rose-300" : "",
          latest?.value != null && latest.value > 0 ? "text-emerald-700 dark:text-emerald-300" : "",
        ].join(" ")}>
          {formatValue(latest?.value, "pct")}
        </div>
      </div>
      <div className="relative mt-3 h-24 rounded bg-muted/70 overflow-hidden">
        <div className="absolute left-0 right-0 top-1/2 h-px bg-border" />
        <div className="absolute inset-x-2 inset-y-2 flex items-stretch gap-1">
          {points.map(point => {
            const value = point.value
            const height = value == null ? 2 : Math.max(3, Math.abs(value) / maxAbs * 42)
            return (
              <div key={point.label} className="relative flex-1" title={`${point.label}: ${formatValue(value, "pct")}`}>
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

function AnnualGrowthTable({ rows }: { rows: FundamentalRow[] }) {
  return (
    <section>
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Annual Growth Focus</h2>
      <div className="border border-border rounded-lg overflow-x-auto bg-card">
        <table className="w-full min-w-[860px] text-sm">
          <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="text-right px-3 py-2 font-medium">Year</th>
              <th className="text-right px-3 py-2 font-medium">Revenue YoY</th>
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
              <tr key={row.fiscal_year} className="hover:bg-muted/30">
                <td className="px-3 py-2 text-right tabular-nums font-medium">{row.fiscal_year}</td>
                <PctCell value={row.revenue_yoy_pct} />
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

function MetricTrendGrid({ rows }: { rows: FundamentalRow[] }) {
  const metrics = [
    { key: "revenue" as const, label: "Revenue", kind: "money" as const },
    { key: "operating_margin_pct" as const, label: "Operating Margin", kind: "pct" as const },
    { key: "free_cash_flow_margin_pct" as const, label: "FCF Margin", kind: "pct" as const },
    { key: "capex_to_revenue_pct" as const, label: "Capex / Revenue", kind: "pct" as const },
    { key: "net_cash" as const, label: "Net Cash", kind: "money" as const },
    { key: "diluted_shares" as const, label: "Diluted Shares", kind: "shares" as const },
  ]
  return (
    <section>
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Trend View</h2>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {metrics.map(metric => (
          <TrendCard key={metric.key} rows={rows} metric={metric} />
        ))}
      </div>
    </section>
  )
}

function TrendCard({
  rows,
  metric,
}: {
  rows: FundamentalRow[]
  metric: { key: keyof FundamentalRow; label: string; kind: "money" | "pct" | "shares" }
}) {
  const values = rows
    .map(row => row[metric.key])
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value))
  const maxAbs = Math.max(1, ...values.map(v => Math.abs(v)))
  return (
    <div className="border border-border rounded-lg bg-card overflow-hidden">
      <div className="px-4 py-2 border-b border-border">
        <div className="text-sm font-semibold">{metric.label}</div>
      </div>
      <div className="p-4 space-y-2">
        {rows.map(row => {
          const raw = row[metric.key]
          const value = typeof raw === "number" ? raw : null
          const width = value == null ? 0 : Math.max(4, Math.abs(value) / maxAbs * 100)
          return (
            <div key={row.fiscal_year} className="grid grid-cols-[44px_1fr_90px] items-center gap-2 text-xs">
              <div className="tabular-nums text-muted-foreground">{row.fiscal_year}</div>
              <div className="h-5 rounded bg-muted overflow-hidden">
                {value != null && (
                  <div
                    className={value < 0 ? "h-full bg-rose-500/45" : "h-full bg-emerald-500/45"}
                    style={{ width: `${width}%` }}
                  />
                )}
              </div>
              <div className="text-right tabular-nums">{formatValue(value, metric.kind)}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function FundamentalTable({ rows }: { rows: FundamentalRow[] }) {
  return (
    <section>
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Annual Fundamentals</h2>
      <div className="border border-border rounded-lg overflow-x-auto bg-card">
        <table className="w-full min-w-[1180px] text-sm">
          <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="text-right px-3 py-2 font-medium">Year</th>
              <th className="text-right px-3 py-2 font-medium">Filed</th>
              <th className="text-right px-3 py-2 font-medium">Timing</th>
              <th className="text-right px-3 py-2 font-medium">React Date</th>
              <th className="text-right px-3 py-2 font-medium">React Ret</th>
              <th className="text-right px-3 py-2 font-medium">Revenue</th>
              <th className="text-right px-3 py-2 font-medium">YoY</th>
              <th className="text-right px-3 py-2 font-medium">Op Margin</th>
              <th className="text-right px-3 py-2 font-medium">Net Income</th>
              <th className="text-right px-3 py-2 font-medium">FCF</th>
              <th className="text-right px-3 py-2 font-medium">FCF Margin</th>
              <th className="text-right px-3 py-2 font-medium">Capex/Rev</th>
              <th className="text-right px-3 py-2 font-medium">Cash+STI</th>
              <th className="text-right px-3 py-2 font-medium">Debt</th>
              <th className="text-right px-3 py-2 font-medium">Net Cash</th>
              <th className="text-right px-3 py-2 font-medium">Debt/FCF</th>
              <th className="text-right px-3 py-2 font-medium">EPS</th>
              <th className="text-right px-3 py-2 font-medium">Shares</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.slice().reverse().map(row => (
              <tr key={row.fiscal_year} className="hover:bg-muted/30">
                <td className="px-3 py-2 text-right tabular-nums font-medium">{row.fiscal_year}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmtDate(row.filed)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatTiming(row.filing_timing)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmtDate(row.reaction_session_date)}</td>
                <PctCell value={row.filing_return_pct} />
                <MoneyCell value={row.revenue} />
                <PctCell value={row.revenue_yoy_pct} />
                <PctCell value={row.operating_margin_pct} neutral />
                <MoneyCell value={row.net_income} />
                <MoneyCell value={row.free_cash_flow} />
                <PctCell value={row.free_cash_flow_margin_pct} neutral />
                <PctCell value={row.capex_to_revenue_pct} neutral />
                <MoneyCell value={row.cash_and_short_term_investments} />
                <MoneyCell value={row.debt} />
                <MoneyCell value={row.net_cash} sign />
                <NumCell value={row.debt_to_fcf} />
                <NumCell value={row.eps_diluted} />
                <td className="px-3 py-2 text-right tabular-nums">{row.diluted_shares != null ? fmtNum(row.diluted_shares / 1e9, 2) + "B" : "n/a"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function QuarterGrowthTable({ rows }: { rows: FundamentalQuarterRow[] }) {
  return (
    <section>
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Quarter Growth Focus</h2>
      <div className="border border-border rounded-lg overflow-x-auto bg-card">
        <table className="w-full min-w-[980px] text-sm">
          <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="text-right px-3 py-2 font-medium">Quarter</th>
              <th className="text-right px-3 py-2 font-medium">Filed</th>
              <th className="text-right px-3 py-2 font-medium">Timing</th>
              <th className="text-right px-3 py-2 font-medium">React Date</th>
              <th className="text-right px-3 py-2 font-medium">React Ret</th>
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
                <td className="px-3 py-2 text-right tabular-nums font-medium">{formatQuarterLabel(row.period_end)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmtDate(row.filed)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatTiming(row.filing_timing)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmtDate(row.reaction_session_date)}</td>
                <PctCell value={row.filing_return_pct} />
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

function QuarterFundamentalTable({ rows }: { rows: FundamentalQuarterRow[] }) {
  return (
    <section>
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Quarter Fundamentals</h2>
      <div className="border border-border rounded-lg overflow-x-auto bg-card">
        <table className="w-full min-w-[1180px] text-sm">
          <thead className="bg-muted/50 text-[10px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="text-right px-3 py-2 font-medium">Quarter</th>
              <th className="text-right px-3 py-2 font-medium">Period End</th>
              <th className="text-right px-3 py-2 font-medium">Filed</th>
              <th className="text-right px-3 py-2 font-medium">Timing</th>
              <th className="text-right px-3 py-2 font-medium">React Date</th>
              <th className="text-right px-3 py-2 font-medium">React Ret</th>
              <th className="text-right px-3 py-2 font-medium">Revenue</th>
              <th className="text-right px-3 py-2 font-medium">YoY</th>
              <th className="text-right px-3 py-2 font-medium">QoQ</th>
              <th className="text-right px-3 py-2 font-medium">Op Margin</th>
              <th className="text-right px-3 py-2 font-medium">Net Income</th>
              <th className="text-right px-3 py-2 font-medium">FCF</th>
              <th className="text-right px-3 py-2 font-medium">FCF Margin</th>
              <th className="text-right px-3 py-2 font-medium">Capex/Rev</th>
              <th className="text-right px-3 py-2 font-medium">Cash+STI</th>
              <th className="text-right px-3 py-2 font-medium">Debt</th>
              <th className="text-right px-3 py-2 font-medium">Net Cash</th>
              <th className="text-right px-3 py-2 font-medium">EPS</th>
              <th className="text-right px-3 py-2 font-medium">Shares</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.slice().reverse().map(row => (
              <tr key={row.period_end} className="hover:bg-muted/30">
                <td className="px-3 py-2 text-right tabular-nums font-medium">{formatQuarterLabel(row.period_end)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmtDate(row.period_end)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmtDate(row.filed)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatTiming(row.filing_timing)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmtDate(row.reaction_session_date)}</td>
                <PctCell value={row.filing_return_pct} />
                <MoneyCell value={row.revenue} />
                <PctCell value={row.revenue_yoy_pct} />
                <PctCell value={row.revenue_qoq_pct} />
                <PctCell value={row.operating_margin_pct} neutral />
                <MoneyCell value={row.net_income} />
                <MoneyCell value={row.free_cash_flow} />
                <PctCell value={row.free_cash_flow_margin_pct} neutral />
                <PctCell value={row.capex_to_revenue_pct} neutral />
                <MoneyCell value={row.cash_and_short_term_investments} />
                <MoneyCell value={row.debt} />
                <MoneyCell value={row.net_cash} sign />
                <NumCell value={row.eps_diluted} />
                <td className="px-3 py-2 text-right tabular-nums">{row.diluted_shares != null ? fmtNum(row.diluted_shares / 1e9, 2) + "B" : "n/a"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function MoneyCell({ value, sign = false }: { value: number | null; sign?: boolean }) {
  const colored = sign && value != null
  return (
    <td className={[
      "px-3 py-2 text-right tabular-nums",
      colored && value < 0 ? "text-rose-600 dark:text-rose-300" : "",
      colored && value > 0 ? "text-emerald-700 dark:text-emerald-300" : "",
    ].join(" ")}>
      {value != null ? fmtNum(value / 1e9, 1) + "B" : "n/a"}
    </td>
  )
}

function PctCell({ value, neutral = false }: { value: number | null; neutral?: boolean }) {
  return (
    <td className="px-3 py-2 text-right tabular-nums">
      {value == null ? "n/a" : (
        <span className={[
          "inline-block min-w-16 rounded px-2 py-1",
          !neutral && value < 0 ? "bg-rose-500/14 text-rose-700 dark:text-rose-300" : "",
          !neutral && value > 0 ? "bg-emerald-500/14 text-emerald-700 dark:text-emerald-300" : "",
        ].join(" ")}>
          {fmtPct(value)}
        </span>
      )}
    </td>
  )
}

function NumCell({ value }: { value: number | null }) {
  return <td className="px-3 py-2 text-right tabular-nums">{value != null ? fmtNum(value, 2) : "n/a"}</td>
}

function formatValue(value: number | null | undefined, kind: "pct" | "num" | "money" | "shares") {
  if (value == null) return "n/a"
  if (kind === "pct") return fmtPct(value)
  if (kind === "money") return fmtNum(value / 1e9, 1) + "B"
  if (kind === "shares") return fmtNum(value / 1e9, 2) + "B"
  return fmtNum(value, 2)
}

function formatQuarterLabel(periodEnd: string) {
  const [year, month] = periodEnd.split("-").map(Number)
  if (!year || !month) return periodEnd
  return `${year} Q${Math.floor((month - 1) / 3) + 1}`
}

function formatTiming(value: string | null | undefined) {
  if (value === "before_open") return "Before open"
  if (value === "market_hours") return "Market"
  if (value === "after_close") return "After close"
  return "n/a"
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
