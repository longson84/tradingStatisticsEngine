import { AnalysisInstrumentSelector } from "@/components/forms/AnalysisInstrumentSelector"
import type { InstrumentCatalogItem } from "@/lib/api"


export function VietnamInstrumentSelector({
  search,
  instruments,
  selectedInstrument,
  total,
  isPending,
  onSearchChange,
  onInstrumentChange,
  onSubmit,
}: {
  search: string
  instruments: InstrumentCatalogItem[]
  selectedInstrument: InstrumentCatalogItem | null
  total?: number
  isPending: boolean
  onSearchChange: (search: string) => void
  onInstrumentChange: (instrument: InstrumentCatalogItem | null) => void
  onSubmit?: () => void
}) {
  return (
    <AnalysisInstrumentSelector
      scope="equity"
      search={search}
      instruments={instruments}
      selectedInstrument={selectedInstrument}
      total={total}
      isPending={isPending}
      onScopeChange={() => undefined}
      onSearchChange={onSearchChange}
      onInstrumentChange={onInstrumentChange}
      onSubmit={onSubmit}
      helperText="Only eligible Vietnam equities are shown."
      hideScope
    />
  )
}
