import { createContext } from "react"

import type { InstrumentCatalogItem, InstrumentScope } from "@/lib/api"

export interface AnalysisContextValue {
  scope: InstrumentScope
  search: string
  instrument: InstrumentCatalogItem | null
  setInstrument: (instrument: InstrumentCatalogItem | null) => void
  changeScope: (scope: InstrumentScope) => void
  changeSearch: (search: string) => void
}

export const AnalysisContext = createContext<AnalysisContextValue | null>(null)
