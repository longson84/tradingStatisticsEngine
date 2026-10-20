import { AnalysisInstrumentSelector } from "@/components/forms/AnalysisInstrumentSelector"
import type { InstrumentCatalogItem } from "@/lib/api"


export function USInstitutionalInstrumentSelector({
  search,
  instruments,
  selectedInstrument,
  total,
  isPending,
  errorMessage,
  onSearchChange,
  onInstrumentChange,
  onSubmit,
}: {
  search: string
  instruments: InstrumentCatalogItem[]
  selectedInstrument: InstrumentCatalogItem | null
  total?: number
  isPending: boolean
  errorMessage?: string
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
      errorMessage={errorMessage}
      emptyMessage="No tracked US equity matches this search."
      onScopeChange={() => undefined}
      onSearchChange={onSearchChange}
      onInstrumentChange={onInstrumentChange}
      onSubmit={onSubmit}
      helperText="US common stocks in the tracked US3000 universe are shown."
      hideScope
    />
  )
}
