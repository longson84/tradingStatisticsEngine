import type { RarityAnalysisResponse, FactorType } from "@/lib/api"
import { fmtDate, fmtInt } from "@/lib/format"
import { ZoneStatsTable } from "./ZoneStatsTable"
import { CurrentStatus } from "./CurrentStatus"
import { ZoneEntryTable } from "./ZoneEntryTable"

interface Props {
  data: RarityAnalysisResponse
  factorType: FactorType
}

export function RarityResults({ data, factorType }: Props) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-baseline gap-3">
        <h2 className="text-xl font-bold text-white">{data.symbol}</h2>
        <span className="text-white/40 text-sm">·</span>
        <span className="text-white/60 text-sm">{data.factor_name}</span>
      </div>

      {/* Analysis timeframe */}
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-white/40">
        <span>Data from <span className="text-white/70">{fmtDate(data.first_date)}</span></span>
        <span>to <span className="text-white/70">{fmtDate(data.last_date)}</span></span>
        <span><span className="text-white/70">{fmtInt(data.total_bars)}</span> sessions</span>
        <span>Stats as of <span className="text-white/70">{fmtDate(data.stats_date)}</span></span>
      </div>

      {/* Zone Statistics */}
      <section>
        <h3 className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Zone Statistics</h3>
        <div className="border border-white/8 rounded-lg overflow-hidden bg-[#161618]">
          <ZoneStatsTable stats={data.zone_stats} />
        </div>
      </section>

      {/* Current Status */}
      <section>
        <h3 className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-3">Current Status</h3>
        <div className="border border-white/8 rounded-lg bg-[#161618] px-5 py-4">
          <CurrentStatus data={data} factorType={factorType} />
        </div>
      </section>

      {/* Zone Entry History */}
      <section>
        <h3 className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">
          Zone Entry History
          <span className="ml-2 text-white/25 font-normal normal-case">
            {data.entries.length} entries
          </span>
        </h3>
        <div className="border border-white/8 rounded-lg overflow-hidden bg-[#161618]">
          <ZoneEntryTable entries={data.entries} />
        </div>
      </section>
    </div>
  )
}
