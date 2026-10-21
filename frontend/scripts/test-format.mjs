import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import ts from "typescript"


process.env.TZ = "Asia/Ho_Chi_Minh"

const source = await readFile(new URL("../src/lib/format.ts", import.meta.url), "utf8")
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const { fmtDate, fmtDateTime } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`)

assert.equal(fmtDate("2026-03-23"), "23/03/26")
assert.equal(fmtDate(null), "—")
assert.equal(fmtDateTime("2026-10-21T00:30:00Z"), "21/10/26 07:30")
assert.equal(fmtDateTime("2026-10-21T09:05:00+07:00"), "21/10/26 09:05")
assert.equal(fmtDateTime(null), "—")
assert.equal(fmtDateTime("not-a-timestamp"), "not-a-timestamp")

console.log("Date formatter contract passed")
