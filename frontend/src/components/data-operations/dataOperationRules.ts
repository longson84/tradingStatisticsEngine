import type {
  DataOperationDataset,
  DataOperationMode,
  DataOperationScopeType,
} from "@/lib/api"


export function requiresInstrumentScope(dataset: DataOperationDataset): boolean {
  return dataset === "session_stats"
}


export function batchDataOperationDatasetOptions(
  scopeType: DataOperationScopeType,
): Array<[DataOperationDataset, string]> {
  const options: Array<[DataOperationDataset, string]> = [
    ["prices", "Prices"],
    ["fundamentals", "Fundamentals"],
  ]
  if (scopeType !== "category") {
    options.push(
      ["foreign_flow", "Foreign flow"],
      ["proprietary_flow", "Proprietary flow"],
    )
  }
  return options
}


export function effectiveDataOperationMode(
  dataset: DataOperationDataset,
  mode: DataOperationMode,
): DataOperationMode {
  return dataset === "session_stats" ? "full" : mode
}


export function dataOperationModeOptions(dataset: DataOperationDataset): string[][] {
  if (dataset === "session_stats") return [["full", "Selected period"]]
  if (dataset === "trade_history") {
    return [
      ["incremental", "Incremental"],
      ["full", "Re-fetch period"],
    ]
  }
  return [
    ["incremental", "Incremental"],
    ["full", "Full history"],
  ]
}


export function isIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith("0000")) return false
  const date = new Date(`${value}T00:00:00Z`)
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value
}


export function buildDataOperationRequest({
  scopeType,
  scopeId,
  dataset,
  mode,
  periodStart,
  periodEnd,
}: {
  scopeType: DataOperationScopeType
  scopeId: string
  dataset: DataOperationDataset
  mode: DataOperationMode
  periodStart: string
  periodEnd: string
}) {
  if (requiresInstrumentScope(dataset) && scopeType !== "instrument") return null
  if (
    scopeType === "category"
    && (dataset === "foreign_flow" || dataset === "proprietary_flow" || dataset === "trade_history")
  ) return null
  const exactPeriod = dataset === "session_stats" || dataset === "trade_history"
  if (exactPeriod && (
    !isIsoDate(periodStart) || !isIsoDate(periodEnd) || periodStart > periodEnd
  )) return null
  return {
    scope_type: scopeType,
    scope_id: scopeId,
    dataset,
    mode: effectiveDataOperationMode(dataset, mode),
    period_start: exactPeriod ? periodStart : null,
    period_end: exactPeriod ? periodEnd : null,
  }
}
