import { FormLabel, FormSelect } from "@/components/forms/FormSelect"
import { useSearchableSelectKeyboard } from "@/components/forms/useSearchableSelectKeyboard"
import type { InstrumentCatalogItem, InstrumentScope } from "@/lib/api"
import { cn } from "@/lib/utils"


const SCOPE_OPTIONS: Array<{ label: string; value: InstrumentScope }> = [
  { label: "Equities", value: "equity" },
  { label: "Crypto Spot", value: "crypto_spot" },
  { label: "Reference Rates", value: "reference_rate" },
  { label: "Market Indices", value: "market_index" },
]


export function AnalysisInstrumentSelector({
  scope,
  search,
  instruments,
  selectedInstrument,
  total,
  isPending,
  onScopeChange,
  onSearchChange,
  onInstrumentChange,
  onSubmit,
  helperText,
  hideHelperText = false,
}: {
  scope: InstrumentScope
  search: string
  instruments: InstrumentCatalogItem[]
  selectedInstrument: InstrumentCatalogItem | null
  total?: number
  isPending: boolean
  onScopeChange: (scope: InstrumentScope) => void
  onSearchChange: (search: string) => void
  onInstrumentChange: (instrument: InstrumentCatalogItem | null) => void
  onSubmit?: () => void
  helperText?: string
  hideHelperText?: boolean
}) {
  const canSearch = search.trim().length >= 3
  const showResults = canSearch && !selectedInstrument && instruments.length > 0
  const keyboard = useSearchableSelectKeyboard({
    items: instruments,
    open: showResults,
    resetKey: `${scope}:${search}`,
    onSelect: onInstrumentChange,
    onEnter: () => {
      if (selectedInstrument) {
        onSubmit?.()
      } else if (instruments.length === 1) {
        onInstrumentChange(instruments[0])
      }
    },
  })
  return (
    <>
      <div>
        <FormLabel>Instrument scope</FormLabel>
        <FormSelect
          value={scope}
          onChange={onScopeChange}
          options={SCOPE_OPTIONS}
        />
      </div>

      <div>
        <FormLabel>Instrument</FormLabel>
        <input
          value={selectedInstrument ? instrumentOptionLabel(selectedInstrument) : search}
          onChange={event => {
            onInstrumentChange(null)
            onSearchChange(event.target.value)
          }}
          onFocus={keyboard.onFocus}
          onKeyDown={keyboard.onKeyDown}
          placeholder={isPending ? "Searching instruments…" : "Symbol, company, asset, or venue"}
          className="w-full rounded border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:border-ring focus:outline-none"
          aria-label="Instrument"
          role="combobox"
          aria-autocomplete="list"
          aria-controls={keyboard.listboxId}
          aria-activedescendant={keyboard.activeOptionId}
          aria-expanded={keyboard.isOpen}
        />
        {keyboard.isOpen && (
          <div
            id={keyboard.listboxId}
            role="listbox"
            aria-label="Instrument results"
            className="mt-1 max-h-56 overflow-y-auto rounded border border-border bg-popover p-1 shadow-md"
          >
            {instruments.map((instrument, index) => (
              <button
                key={instrument.id}
                id={keyboard.optionId(index)}
                ref={keyboard.optionRef(index)}
                type="button"
                role="option"
                aria-selected={keyboard.activeIndex === index}
                onClick={() => onInstrumentChange(instrument)}
                onMouseEnter={() => keyboard.setActiveIndex(index)}
                className={cn(
                  "block w-full rounded px-2 py-2 text-left text-sm text-popover-foreground hover:bg-accent hover:text-accent-foreground",
                  keyboard.activeIndex === index && "bg-accent text-accent-foreground",
                )}
              >
                <span className="block font-medium">{instrument.symbol}</span>
                <span className="block truncate text-xs text-muted-foreground">
                  {instrumentDetailLabel(instrument)}
                </span>
              </button>
            ))}
          </div>
        )}
        {!hideHelperText && (
          <p className="mt-1 text-[10px] text-muted-foreground">
            {helperText ?? (!selectedInstrument && !canSearch
              ? "Type at least 3 characters to search PostgreSQL instruments."
              : total != null
              ? `${total.toLocaleString()} analysis-ready instruments with PostgreSQL price history.`
              : "Only instruments with canonical stored price history are shown.")}
          </p>
        )}
      </div>
    </>
  )
}


function instrumentOptionLabel(instrument: InstrumentCatalogItem): string {
  const identity = instrument.company_name
    ?? (instrument.base_asset && instrument.quote_asset
      ? `${instrument.base_asset}/${instrument.quote_asset}`
      : instrumentTypeLabel(instrument.instrument_type))
  const location = instrument.venue_name
  return [instrument.symbol, identity, location, instrument.currency]
    .filter(Boolean)
    .join(" · ")
}


function instrumentDetailLabel(instrument: InstrumentCatalogItem): string {
  const identity = instrument.company_name
    ?? (instrument.base_asset && instrument.quote_asset
      ? `${instrument.base_asset}/${instrument.quote_asset}`
      : instrumentTypeLabel(instrument.instrument_type))
  return [identity, instrument.venue_name, instrument.currency]
    .filter(Boolean)
    .join(" · ")
}


function instrumentTypeLabel(instrumentType: string): string {
  if (instrumentType === "common_stock") return "Equity"
  if (instrumentType === "spot") return "Crypto spot"
  if (instrumentType === "reference_rate") return "Reference rate"
  if (instrumentType === "market_index") return "Market index"
  return instrumentType.replaceAll("_", " ")
}
