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
  const { TurnoverIntensityAnalytics } = await server.ssrLoadModule(
    "/src/components/trading-activity/TurnoverIntensityAnalytics.tsx",
  )
  const html = renderToStaticMarkup(React.createElement(TurnoverIntensityAnalytics, {
    analysis: {
      formula_version: "turnover_intensity_v1",
      baseline_sessions: 20,
      points: [
        {
          trading_date: "2026-09-01", intensity: 0.01,
          baseline: null, anomaly_score: null,
          unavailable_reason: "insufficient_history",
        },
        {
          trading_date: "2026-09-02", intensity: null,
          baseline: null, anomaly_score: null,
          unavailable_reason: "invalid_market_cap",
        },
        {
          trading_date: "2026-09-03", intensity: 0.015,
          baseline: 0.01, anomaly_score: null,
          unavailable_reason: "zero_baseline_variance",
        },
        {
          trading_date: "2026-09-04", intensity: 0.025,
          baseline: 0.015, anomaly_score: 2,
          unavailable_reason: null,
        },
      ],
    },
  }))

  assert.match(html, /Turnover intensity analytics/)
  assert.match(html, /Latest intensity/)
  assert.match(html, /2\.50%/)
  assert.match(html, /Latest anomaly/)
  assert.match(html, /\+2\.00σ/)
  assert.match(html, /role="img" aria-label="Turnover intensity and prior 20-session baseline"/)
  assert.match(html, /role="img" aria-label="Turnover intensity anomaly score"/)
  assert.match(html, /Not available/)
  assert.match(html, /Fewer than 20 prior stored sessions/)
  assert.match(html, /Market capitalization is invalid/)
  assert.match(html, /Prior 20-session window has no variation/)
  assert.match(html, /2026-09-03: intensity 1\.50%, baseline 1\.00%, anomaly Not available — Prior 20-session window has no variation/)
  assert.match(html, /Calculated from stored activity only/)

  const isolatedHtml = renderToStaticMarkup(React.createElement(TurnoverIntensityAnalytics, {
    analysis: {
      formula_version: "turnover_intensity_v1",
      baseline_sessions: 20,
      points: [{
        trading_date: "2026-09-21", intensity: 0.025,
        baseline: 0.015, anomaly_score: 1.5,
        unavailable_reason: null,
      }],
    },
  }))
  assert.match(isolatedHtml, /data-series="intensity"/)
  assert.match(isolatedHtml, /data-series="baseline"/)
  console.log("Turnover intensity analytics contract passed")
} finally {
  await server.close()
}
