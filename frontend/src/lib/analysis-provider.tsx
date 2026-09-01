import { useMemo, useState, type ReactNode } from "react"

import type { InstrumentCatalogItem, InstrumentScope } from "@/lib/api"
import { AnalysisContext, type AnalysisContextValue } from "@/lib/analysis-context"

export function AnalysisContextProvider({ children }: { children: ReactNode }) {
  const [scope, setScope] = useState<InstrumentScope>("equity")
  const [search, setSearch] = useState("")
  const [instrument, setInstrument] = useState<InstrumentCatalogItem | null>(null)

  const value = useMemo<AnalysisContextValue>(() => ({
    scope,
    search,
    instrument,
    setInstrument,
    changeScope: nextScope => {
      setScope(nextScope)
      setSearch("")
      setInstrument(null)
    },
    changeSearch: nextSearch => {
      setSearch(nextSearch)
      setInstrument(null)
    },
  }), [instrument, scope, search])

  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>
}
