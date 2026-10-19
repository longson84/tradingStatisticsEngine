import assert from "node:assert/strict"
import React from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { MemoryRouter } from "react-router"
import { createServer } from "vite"


const server = await createServer({
  appType: "custom",
  optimizeDeps: { noDiscovery: true },
  server: { middlewareMode: true, hmr: false },
})

try {
  const { TradingActivityScannerResults } = await server.ssrLoadModule(
    "/src/components/trading-activity/TradingActivityScannerResults.tsx",
  )
  const result = {
    scope_type: "universe", scope_id: "VN100", scope_name: "VN100 Index",
    target_session: "2026-10-19", formula_version: "turnover_intensity_v1",
    baseline_sessions: 20,
    counts: { current: 1, stale: 1, insufficient_history: 1, unavailable: 1 },
    items: [
      { instrument_id: 42, symbol: "FPT", display_name: "FPT Corp", venue_code: "HOSE", status: "current", rank: 1, latest_session: "2026-10-19", turnover_intensity: 0.0125, baseline: 0.01, anomaly_score: 2.5, unavailable_reason: null },
      { instrument_id: 43, symbol: "VNM", display_name: "Vinamilk", venue_code: "HOSE", status: "stale", rank: null, latest_session: "2026-10-18", turnover_intensity: 0.009, baseline: 0.008, anomaly_score: 1, unavailable_reason: null },
      { instrument_id: 44, symbol: "VCB", display_name: "Vietcombank", venue_code: "HOSE", status: "insufficient_history", rank: null, latest_session: "2026-10-19", turnover_intensity: 0.008, baseline: null, anomaly_score: null, unavailable_reason: "insufficient_history" },
      { instrument_id: 45, symbol: "AAPL", display_name: "Apple", venue_code: "NASDAQ", status: "unavailable", rank: null, latest_session: null, turnover_intensity: null, baseline: null, anomaly_score: null, unavailable_reason: "unsupported_instrument" },
    ],
  }
  const html = renderToStaticMarkup(React.createElement(
    MemoryRouter,
    null,
    React.createElement(TradingActivityScannerResults, { result }),
  ))

  assert.match(html, /Latest stored completed session/)
  assert.match(html, /19\/10\/26/)
  assert.match(html, /Current ranked activity/)
  assert.match(html, /Stale observations/)
  assert.match(html, /Insufficient 20-session history/)
  assert.match(html, /Unavailable/)
  assert.match(html, /1\.25%/)
  assert.match(html, /\+2\.50σ/)
  assert.match(html, /href="\/vietnam-market\/trading-activity\?instrument_id=42&amp;symbol=FPT"/)
  assert.match(html, /No provider calls/)
  console.log("Trading activity scanner contract passed")
} finally {
  await server.close()
}
