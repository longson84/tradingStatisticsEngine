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
  assert.equal(rules.requiresInstrumentScope("foreign_flow"), true)
  assert.equal(rules.requiresInstrumentScope("trade_history"), false)
  assert.equal(rules.effectiveDataOperationMode("session_stats", "incremental"), "full")
  assert.equal(rules.effectiveDataOperationMode("trade_history", "incremental"), "incremental")
  assert.equal(rules.effectiveDataOperationMode("trade_history", "full"), "full")
  assert.deepEqual(rules.dataOperationModeOptions("trade_history"), [
    ["incremental", "Incremental"],
    ["full", "Re-fetch period"],
  ])
  console.log("Trading activity batch refresh UI rules passed")
} finally {
  await server.close()
}
