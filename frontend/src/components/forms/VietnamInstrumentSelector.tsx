import { AnalysisInstrumentSelector } from "@/components/forms/AnalysisInstrumentSelector"
import type { InstrumentCatalogItem } from "@/lib/api"


export function VietnamInstrumentSelector({
  search,
  instruments,
  selectedInstrument,
  total,
  isPending,
  errorMessage,
  emptyMessage,
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
  emptyMessage?: string
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
      emptyMessage={emptyMessage}
      onScopeChange={() => undefined}
      onSearchChange={onSearchChange}
      onInstrumentChange={onInstrumentChange}
      onSubmit={onSubmit}
      helperText="Only eligible Vietnam equities are shown."
      hideScope
    />
  )
}
