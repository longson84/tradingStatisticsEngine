import assert from "node:assert/strict"
import React from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { createServer } from "vite"


const server = await createServer({
  appType: "custom",
  server: { middlewareMode: true },
})

try {
  const { VietnamInstrumentSelector } = await server.ssrLoadModule(
    "/src/components/forms/VietnamInstrumentSelector.tsx",
  )
  const instruments = [
    {
      id: 1,
      symbol: "FPT",
      instrument_type: "common_stock",
      venue_code: "HOSE",
      venue_name: "Ho Chi Minh Stock Exchange",
      currency: "VND",
      company_name: "FPT Corporation",
      base_asset: null,
      quote_asset: null,
    },
    {
      id: 2,
      symbol: "ACB",
      instrument_type: "common_stock",
      venue_code: "HOSE",
      venue_name: "Ho Chi Minh Stock Exchange",
      currency: "VND",
      company_name: "Asia Commercial Bank",
      base_asset: null,
      quote_asset: null,
    },
  ]
  const html = renderToStaticMarkup(React.createElement(VietnamInstrumentSelector, {
    search: "FPT",
    instruments,
    selectedInstrument: null,
    total: 2,
    isPending: false,
    onSearchChange() {},
    onInstrumentChange() {},
  }))

  assert.doesNotMatch(html, /Instrument scope/)
  assert.doesNotMatch(html, /<select/)
  assert.match(html, /role="combobox"/)
  assert.match(html, /aria-autocomplete="list"/)
  assert.match(html, /aria-expanded="true"/)
  assert.match(html, /role="listbox"/)
  assert.match(html, /role="option"/)
  assert.match(html, /Only eligible Vietnam equities are shown/)
  console.log("Vietnam Instrument selector contract passed")
} finally {
  await server.close()
}
