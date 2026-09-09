import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

/**
 * Ports: this project owns the 8xxx block.
 *
 * Several projects are developed on this machine at once, so a machine-wide
 * convention keeps them apart: one thousand-block per app, API at BASE+1, web
 * dev at BASE+173 ("173" for Vite), preview at BASE+174. Blocks as of
 * 2026-09-09 — eravntrans 3xxx, a Python app 4xxx, totha 6xxx, an ERP base
 * 7xxx, this project 8xxx, personal-hq 9xxx. 5xxx is databases only, which is
 * why the web port is no longer 5174: that is Vite's own default, another
 * project on this machine hard-coded the same number, and with no strictPort
 * the second one to start renumbered itself in silence.
 *
 * The API moves 8000 -> 8001 so the block reads consistently; Postgres stays
 * on 5436. macOS ControlCenter answers on 5000 and 7000, avoided everywhere.
 */
const WEB_PORT = 8173
const PREVIEW_PORT = 8174

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // strictPort, which was missing: Vite's default is to move quietly to the
  // next free port, and on this machine the next free port belongs to another
  // project. A refused start is the better failure.
  server: {
    port: WEB_PORT,
    strictPort: true,
  },
  preview: {
    port: PREVIEW_PORT,
    strictPort: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
