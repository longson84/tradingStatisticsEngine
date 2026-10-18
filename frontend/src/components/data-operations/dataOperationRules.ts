import type { DataOperationDataset, DataOperationMode } from "@/lib/api"


export function requiresInstrumentScope(dataset: DataOperationDataset): boolean {
  return dataset === "foreign_flow"
    || dataset === "proprietary_flow"
    || dataset === "session_stats"
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
