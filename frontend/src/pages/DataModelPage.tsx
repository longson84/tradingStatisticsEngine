import {
  ArrowDown,
  ArrowRight,
  Binary,
  Blocks,
  Building2,
  CircleDollarSign,
  Database,
  Landmark,
  ListTree,
  MapPin,
  Network,
  Tag,
} from "lucide-react"
import { Sidebar } from "@/components/Sidebar"
import { Badge } from "@/components/ui/badge"


const entities = [
  {
    name: "Company",
    icon: Building2,
    definition: "A legal or economic issuer, not something directly traded.",
    examples: "Alphabet Inc., Apple Inc.",
    stores: "Name, country, sector, industry, stable identifiers",
  },
  {
    name: "Asset",
    icon: CircleDollarSign,
    definition: "The venue-independent economic thing that exists or carries value.",
    examples: "Alphabet Class A, BTC, USD, USDT",
    stores: "Canonical code, asset type, network and contract identity",
  },
  {
    name: "Instrument",
    icon: Blocks,
    definition: "A specific tradable product or observable market relationship.",
    examples: "NASDAQ GOOGL, Binance BTC/USDT, Yahoo BTC-USD",
    stores: "Type, asset roles, venue, currency, trading rules, active state",
  },
  {
    name: "Symbol",
    icon: Tag,
    definition: "A name assigned to an instrument inside a particular namespace.",
    examples: "GOOGL, BTCUSDT, BTC-USDT, BTC-USD",
    stores: "Namespace, symbol, primary flag, valid-from and valid-to dates",
  },
  {
    name: "Venue",
    icon: Landmark,
    definition: "The economic location where trades occur—not the data provider.",
    examples: "NASDAQ, Binance Spot, future OKX Spot",
    stores: "Stable code, display name, venue type, country, active state",
  },
  {
    name: "Observation",
    icon: Database,
    definition: "A dated fact collected for an instrument, with its provenance.",
    examples: "Daily OHLCV bar for Binance BTC/USDT on 2026-08-08",
    stores: "Session, values, price basis, source and fetched time",
  },
  {
    name: "Universe",
    icon: ListTree,
    definition: "A named collection whose membership points to instruments.",
    examples: "S&P 500, Nasdaq 100, VN30, Binance Spot",
    stores: "Name, market, description, source and many-to-many membership",
  },
]

const assetTypes = [
  ["equity", "Ownership interest or share class", "Alphabet Class A"],
  ["crypto", "Native or tokenized crypto asset", "BTC, ETH"],
  ["fiat", "Government-issued currency", "USD, VND"],
  ["stablecoin", "Token targeting a reference currency", "USDT, USDC"],
]

const instrumentTypes = [
  ["common_stock", "Tradable equity security", "NASDAQ GOOGL", "Current"],
  ["spot", "Venue-specific exchange of base for quote", "Binance BTC/USDT", "Current"],
  ["reference_rate", "Provider-defined observation without an execution venue", "Yahoo BTC-USD", "Next"],
]


export function DataModelPage() {
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar className="w-72" />
      <main className="min-w-0 flex-1 overflow-y-auto p-6 lg:p-8">
        <div className="mx-auto max-w-7xl space-y-8">
          <header className="flex flex-col justify-between gap-4 border-b border-border pb-6 lg:flex-row lg:items-end">
            <div>
              <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                <Network size={13} />
                Build · Canonical domain reference
              </div>
              <h1 className="text-3xl font-bold tracking-tight">Data Model</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                The durable taxonomy for companies, assets, instruments, symbols, venues,
                observations, and their data provenance.
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <Badge variant="secondary">Current model</Badge>
              <Badge variant="outline">Next extension</Badge>
            </div>
          </header>

          <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              Remember this sentence
            </div>
            <p className="mt-3 max-w-5xl text-lg font-medium leading-8">
              A company may issue an asset; an instrument makes assets tradable or observable;
              a symbol names that instrument in one namespace; a venue says where it trades;
              and provenance says where each observation came from.
            </p>
          </section>

          <section className="space-y-3">
            <SectionHeading
              eyebrow="Relationship map"
              title="Identity flows from issuer to observation"
              description="Optional relationships are deliberately optional: BTC has no company, and a reference rate has no execution venue."
            />
            <div className="overflow-x-auto rounded-xl border border-border bg-card p-5">
              <div className="mx-auto flex min-w-[900px] items-center justify-center gap-3">
                <FlowNode label="Company" detail="issuer identity" icon={Building2} />
                <FlowArrow label="issues" />
                <FlowNode label="Asset" detail="economic identity" icon={CircleDollarSign} />
                <FlowArrow label="base · quote · settlement" />
                <FlowNode label="Instrument" detail="product identity" icon={Blocks} strong />
                <FlowArrow label="named by" />
                <FlowNode label="Symbol" detail="namespace identity" icon={Tag} />
              </div>
              <div className="mx-auto mt-5 grid min-w-[900px] max-w-4xl grid-cols-[1fr_auto_1fr_auto_1fr] items-center gap-3">
                <FlowNode label="Venue" detail="where it trades" icon={Landmark} />
                <ArrowRight size={18} className="text-muted-foreground" />
                <FlowNode label="Instrument" detail="the join point" icon={Blocks} strong />
                <ArrowRight size={18} className="text-muted-foreground" />
                <FlowNode label="Price bars" detail="dated observations" icon={Database} />
              </div>
              <div className="mt-4 flex min-w-[900px] items-center justify-center gap-2 text-xs text-muted-foreground">
                <MapPin size={13} />
                Venue is optional for reference rates. Company is optional for decentralized assets.
              </div>
            </div>
          </section>

          <section className="space-y-3">
            <SectionHeading
              eyebrow="Entity glossary"
              title="What each record means"
              description="Use these nouns precisely; similar-looking values can represent different identities."
            />
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {entities.map(entity => (
                <EntityCard key={entity.name} {...entity} />
              ))}
            </div>
          </section>

          <section className="grid gap-5 xl:grid-cols-2">
            <TaxonomyTable
              eyebrow="Asset taxonomy"
              title="What kind of economic asset is it?"
              columns={["Type", "Meaning", "Example"]}
              rows={assetTypes}
            />
            <TaxonomyTable
              eyebrow="Instrument taxonomy"
              title="What kind of product or rate is it?"
              columns={["Type", "Meaning", "Example", "Status"]}
              rows={instrumentTypes}
              statusColumn
            />
          </section>

          <section className="space-y-3">
            <SectionHeading
              eyebrow="Worked examples"
              title="Three paths through the same model"
              description="The structure stays stable even when companies, venues, and providers differ."
            />
            <div className="grid gap-4 xl:grid-cols-3">
              <ExampleCard
                number="01"
                title="Listed equity"
                subtitle="Alphabet Class A on NASDAQ"
                lines={[
                  ["Company", "Alphabet Inc."],
                  ["Asset", "Alphabet Class A · equity"],
                  ["Instrument", "NASDAQ common stock"],
                  ["Symbol", "GOOGL · canonical/yfinance"],
                  ["Venue", "NASDAQ"],
                  ["Observation", "Adjusted or unadjusted daily bars"],
                ]}
              />
              <ExampleCard
                number="02"
                title="Crypto spot"
                subtitle="Bitcoin traded against Tether"
                lines={[
                  ["Company", "None for decentralized BTC"],
                  ["Assets", "BTC · crypto / USDT · stablecoin"],
                  ["Instrument", "BTC/USDT · spot"],
                  ["Symbol", "BTCUSDT · Binance namespace"],
                  ["Venue", "Binance Spot"],
                  ["Observation", "Venue-unadjusted Binance bars"],
                ]}
              />
              <ExampleCard
                number="03"
                title="Reference rate"
                subtitle="Yahoo Finance Bitcoin / US Dollar"
                status="Next extension"
                lines={[
                  ["Company", "None"],
                  ["Assets", "BTC · crypto / USD · fiat"],
                  ["Instrument", "BTC/USD · reference_rate"],
                  ["Symbol", "BTC-USD · Yahoo namespace"],
                  ["Venue", "None; it is not an order book"],
                  ["Observation", "Provider-unspecified Yahoo bars"],
                ]}
              />
            </div>
          </section>

          <section className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-xl border border-border bg-card p-5">
              <div className="flex items-center gap-2">
                <Binary size={16} />
                <h2 className="text-sm font-semibold">Venue and provenance are separate</h2>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <Definition label="Venue" value="Where economic trading occurred" example="Binance Spot" />
                <Definition label="Source / provider" value="Where we obtained an observation" example="Binance archive, Binance REST, Yahoo Finance" />
              </div>
              <p className="mt-4 text-sm leading-6 text-muted-foreground">
                A provider can disappear or be replaced without changing the identity of the venue
                instrument. Provider names remain open provenance strings; there is intentionally no
                provider foreign-key catalog.
              </p>
            </div>
            <div className="rounded-xl border border-border bg-muted/30 p-5">
              <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                Never conflate
              </div>
              <ul className="mt-4 space-y-3 text-sm">
                <Rule>Company with instrument</Rule>
                <Rule>Asset code with permanent identity</Rule>
                <Rule>Data provider with trading venue</Rule>
                <Rule>BTC/USD reference rate with BTC/USDT spot</Rule>
                <Rule>One venue&apos;s bars with a global crypto price</Rule>
              </ul>
            </div>
          </section>

          <footer className="border-t border-border py-5 text-xs leading-5 text-muted-foreground">
            PostgreSQL is authoritative. JSON and CSV may be ingestion inputs, but they are not the
            application&apos;s canonical company, instrument, or price store.
          </footer>
        </div>
      </main>
    </div>
  )
}


function SectionHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string
  title: string
  description: string
}) {
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
        {eyebrow}
      </div>
      <h2 className="mt-1 text-lg font-semibold tracking-tight">{title}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
    </div>
  )
}


function FlowNode({
  label,
  detail,
  icon: Icon,
  strong = false,
}: {
  label: string
  detail: string
  icon: React.ComponentType<{ size?: number; className?: string }>
  strong?: boolean
}) {
  return (
    <div className={strong ? "min-w-44 rounded-lg bg-primary p-4 text-primary-foreground" : "min-w-44 rounded-lg border border-border bg-background p-4"}>
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Icon size={15} />
        {label}
      </div>
      <div className={strong ? "mt-1 text-xs text-primary-foreground/70" : "mt-1 text-xs text-muted-foreground"}>
        {detail}
      </div>
    </div>
  )
}


function FlowArrow({ label }: { label: string }) {
  return (
    <div className="flex min-w-24 flex-col items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground">
      <span>{label}</span>
      <ArrowRight size={18} />
    </div>
  )
}


function EntityCard({
  name,
  icon: Icon,
  definition,
  examples,
  stores,
}: (typeof entities)[number]) {
  return (
    <article className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-2">
        <div className="rounded-md bg-muted p-2"><Icon size={16} /></div>
        <h3 className="font-semibold">{name}</h3>
      </div>
      <p className="mt-4 text-sm leading-6">{definition}</p>
      <dl className="mt-4 space-y-3 text-xs">
        <div>
          <dt className="font-medium text-muted-foreground">Examples</dt>
          <dd className="mt-1">{examples}</dd>
        </div>
        <div>
          <dt className="font-medium text-muted-foreground">Stores</dt>
          <dd className="mt-1">{stores}</dd>
        </div>
      </dl>
    </article>
  )
}


function TaxonomyTable({
  eyebrow,
  title,
  columns,
  rows,
  statusColumn = false,
}: {
  eyebrow: string
  title: string
  columns: string[]
  rows: string[][]
  statusColumn?: boolean
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="border-b border-border p-5">
        <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
          {eyebrow}
        </div>
        <h2 className="mt-1 text-base font-semibold">{title}</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[540px] text-left text-sm">
          <thead className="bg-muted/50 text-[10px] uppercase tracking-wider text-muted-foreground">
            <tr>{columns.map(column => <th key={column} className="px-4 py-3 font-semibold">{column}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map(row => (
              <tr key={row[0]}>
                {row.map((cell, index) => (
                  <td key={`${row[0]}-${columns[index]}`} className="px-4 py-3 align-top">
                    {index === 0 ? <code className="text-xs font-semibold">{cell}</code> : null}
                    {index !== 0 && statusColumn && index === row.length - 1
                      ? <Badge variant={cell === "Current" ? "secondary" : "outline"}>{cell}</Badge>
                      : index !== 0 && <span className="text-muted-foreground">{cell}</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}


function ExampleCard({
  number,
  title,
  subtitle,
  lines,
  status,
}: {
  number: string
  title: string
  subtitle: string
  lines: string[][]
  status?: string
}) {
  return (
    <article className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">{number}</div>
          <h3 className="mt-1 font-semibold">{title}</h3>
          <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
        </div>
        {status && <Badge variant="outline">{status}</Badge>}
      </div>
      <dl className="mt-5 space-y-0">
        {lines.map(([label, value], index) => (
          <div key={label} className="grid grid-cols-[88px_1fr] gap-3">
            <div className="flex flex-col items-center">
              <div className="flex h-6 w-6 items-center justify-center rounded-full border border-border bg-background text-[10px] font-medium">
                {index + 1}
              </div>
              {index < lines.length - 1 && <ArrowDown size={13} className="my-1 text-muted-foreground/50" />}
            </div>
            <div className={index < lines.length - 1 ? "pb-3" : ""}>
              <dt className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</dt>
              <dd className="mt-0.5 text-sm">{value}</dd>
            </div>
          </div>
        ))}
      </dl>
    </article>
  )
}


function Definition({ label, value, example }: { label: string; value: string; example: string }) {
  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <div className="text-xs font-semibold">{label}</div>
      <div className="mt-2 text-sm">{value}</div>
      <div className="mt-2 text-xs text-muted-foreground">Example: {example}</div>
    </div>
  )
}


function Rule({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-center gap-3">
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-foreground" />
      {children}
    </li>
  )
}
