import assert from "node:assert/strict"
import fs from "node:fs"


const source = fs.readFileSync(
  new URL("../src/pages/DataOperationsPage.tsx", import.meta.url),
  "utf8",
)

assert.match(
  source,
  /className="mt-2 flex flex-wrap gap-2"/,
  "operation choices must wrap instead of overflowing into the adjacent column",
)

console.log("Data Operations responsive layout contract passed")
