import assert from "node:assert/strict"
import { createServer } from "vite"


const server = await createServer({
  appType: "custom",
  optimizeDeps: { noDiscovery: true },
  server: { middlewareMode: true, hmr: false },
})

try {
  const rules = await server.ssrLoadModule(
    "/src/components/data-operations/dataOperationRules.ts",
  )

  assert.equal(rules.requiresInstrumentScope("session_stats"), true)
  assert.equal(rules.requiresInstrumentScope("foreign_flow"), false)
  assert.equal(rules.requiresInstrumentScope("proprietary_flow"), false)
  assert.equal(rules.requiresInstrumentScope("trade_history"), false)
  assert.equal(rules.effectiveDataOperationMode("session_stats", "incremental"), "full")
  assert.equal(rules.effectiveDataOperationMode("trade_history", "incremental"), "incremental")
  assert.equal(rules.effectiveDataOperationMode("trade_history", "full"), "full")
  assert.deepEqual(rules.dataOperationModeOptions("trade_history"), [
    ["incremental", "Incremental"],
    ["full", "Re-fetch period"],
  ])
  assert.deepEqual(rules.buildDataOperationRequest({
    scopeType: "universe",
    scopeId: "VN100",
    dataset: "trade_history",
    mode: "incremental",
    periodStart: "2026-10-01",
    periodEnd: "2026-10-16",
  }), {
    scope_type: "universe",
    scope_id: "VN100",
    dataset: "trade_history",
    mode: "incremental",
    period_start: "2026-10-01",
    period_end: "2026-10-16",
  })
  assert.deepEqual(rules.buildDataOperationRequest({
    scopeType: "universe",
    scopeId: "VN100",
    dataset: "foreign_flow",
    mode: "incremental",
    periodStart: "",
    periodEnd: "",
  }), {
    scope_type: "universe",
    scope_id: "VN100",
    dataset: "foreign_flow",
    mode: "incremental",
    period_start: null,
    period_end: null,
  })
  assert.deepEqual(rules.buildDataOperationRequest({
    scopeType: "watchlist",
    scopeId: "7",
    dataset: "proprietary_flow",
    mode: "full",
    periodStart: "",
    periodEnd: "",
  }), {
    scope_type: "watchlist",
    scope_id: "7",
    dataset: "proprietary_flow",
    mode: "full",
    period_start: null,
    period_end: null,
  })
  assert.equal(rules.buildDataOperationRequest({
    scopeType: "category",
    scopeId: "equity",
    dataset: "foreign_flow",
    mode: "incremental",
    periodStart: "",
    periodEnd: "",
  }), null)
  assert.deepEqual(
    rules.batchDataOperationDatasetOptions("universe").map(([value]) => value),
    ["prices", "fundamentals", "foreign_flow", "proprietary_flow"],
  )
  assert.deepEqual(
    rules.batchDataOperationDatasetOptions("category").map(([value]) => value),
    ["prices", "fundamentals"],
  )
  assert.equal(rules.buildDataOperationRequest({
    scopeType: "watchlist",
    scopeId: "7",
    dataset: "session_stats",
    mode: "full",
    periodStart: "2026-10-01",
    periodEnd: "2026-10-16",
  }), null)
  console.log("Trading activity batch refresh UI rules passed")
} finally {
  await server.close()
}
