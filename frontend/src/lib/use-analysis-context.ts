import { useContext } from "react"

import { AnalysisContext, type AnalysisContextValue } from "@/lib/analysis-context"

export function useAnalysisContext(): AnalysisContextValue {
  const value = useContext(AnalysisContext)
  if (!value) throw new Error("useAnalysisContext must be used inside AnalysisContextProvider")
  return value
}
