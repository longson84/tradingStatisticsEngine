import type { RarityAnalysisResponse, FactorType } from "@/lib/api"
import { fmtDate, fmtInt } from "@/lib/format"
import { ZoneStatsTable } from "./ZoneStatsTable"
import { CurrentStatus } from "./CurrentStatus"
import { ZoneEntryTable } from "./ZoneEntryTable"
import { PriceFactorChart } from "./PriceFactorChart"
import { EventStudyChart } from "./EventStudyChart"

interface Props {
  data: RarityAnalysisResponse
  factorType: FactorType
}

export function RarityResults({ data, factorType }: Props) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 pb-4 border-b border-border">
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-bold tracking-tight text-foreground">{data.symbol}</h2>
          <span className="text-xs font-mono px-2 py-0.5 rounded border border-border bg-muted text-muted-foreground uppercase tracking-wider">
            {data.factor_name}
          </span>
        </div>
        <div className="ml-auto flex items-center gap-4 text-xs text-muted-foreground/60">
          <span>{fmtDate(data.first_date)} – {fmtDate(data.last_date)}</span>
          <span className="tabular-nums">{fmtInt(data.total_bars)} sessions</span>
          <span>as of {fmtDate(data.stats_date)}</span>
        </div>
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-2 gap-4">
        <PriceFactorChart
          timeSeries={data.time_series}
          zoneStats={data.zone_stats}
          entries={data.entries}
        />
        <EventStudyChart zones={data.event_study} />
      </div>

      {/* Zone Statistics */}
      <section>
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Zone Statistics</h3>
        <div className="border border-border rounded-lg overflow-hidden bg-card">
          <ZoneStatsTable stats={data.zone_stats} />
        </div>
      </section>

      {/* Current Status */}
      <section>
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Current Status</h3>
        <div className="border border-border rounded-lg bg-card px-5 py-4">
          <CurrentStatus data={data} factorType={factorType} />
        </div>
      </section>

      {/* Zone Entry History */}
      <section>
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
          Zone Entry History
          <span className="ml-2 text-muted-foreground/50 font-normal normal-case">
            {data.entries.length} entries
          </span>
        </h3>
        <div className="border border-border rounded-lg overflow-hidden bg-card">
          <ZoneEntryTable entries={data.entries} />
        </div>
      </section>
    </div>
  )
}
