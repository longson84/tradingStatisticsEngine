import assert from "node:assert/strict"
import React from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { createServer } from "vite"


const server = await createServer({
  appType: "custom",
  optimizeDeps: { noDiscovery: true },
  server: { middlewareMode: true, hmr: false },
})

try {
  const { InstitutionalActivityView } = await server.ssrLoadModule(
    "/src/components/institutional-activity/InstitutionalActivityView.tsx",
  )
  const available = {
    status: "available", message: null, instrument_id: 42, symbol: "AAPL",
    instrument_type: "common_stock", venue_code: "NASDAQ",
    formula_version: "institutional_position_change_v1",
    latest_report_period: "2026-06-30", latest_available_at: "2026-08-14T16:30:00Z",
    action_counts: { new: 1, added: 1, unchanged: 0, reduced: 0, exited: 1 },
    history: [
      { report_period: "2026-03-31", holder_count: 2, total_shares: 150 },
      { report_period: "2026-06-30", holder_count: 2, total_shares: 200 },
    ],
    changes: [{
      manager_id: 1, manager_name: "Berkshire Hathaway", is_curated: true,
      action: "added", previous_shares: 100, current_shares: 125,
      share_change: 25, percentage_change: 25, report_period: "2026-06-30",
      available_at: "2026-08-14T16:30:00Z", availability_precision: "accepted_at",
      source_url: "https://www.sec.gov/filing/1",
    }],
    current_holders: [{
      manager_id: 1, manager_name: "Berkshire Hathaway", is_curated: true,
      shares: 125, report_period: "2026-06-30", available_at: "2026-08-14T16:30:00Z",
      availability_precision: "accepted_at", source_url: "https://www.sec.gov/filing/1",
    }],
  }
  const html = renderToStaticMarkup(React.createElement(InstitutionalActivityView, {
    result: available,
  }))
  assert.match(html, /Reported position changes/)
  assert.match(html, /Holdings as of/)
  assert.match(html, /Filed data available/)
  assert.match(html, /Reported shares by quarter/)
  assert.match(html, /Berkshire Hathaway/)
  assert.match(html, /Curated manager/)
  assert.match(html, /Added/)
  assert.match(html, /href="https:\/\/www.sec.gov\/filing\/1"/)
  assert.match(html, /not confirmed executions/i)

  const unavailableHtml = renderToStaticMarkup(React.createElement(
    InstitutionalActivityView,
    { result: { ...available, status: "missing_identifier", message: "No verified CUSIP mapping is stored", history: [], changes: [], current_holders: [] } },
  ))
  assert.match(unavailableHtml, /role="status"/)
  assert.match(unavailableHtml, /No verified CUSIP mapping is stored/)
  console.log("Institutional Activity contract passed")
} finally {
  await server.close()
}
