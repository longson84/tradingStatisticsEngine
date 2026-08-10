import { ChevronLeft, ChevronRight } from "lucide-react"


export function Pagination({
  total,
  offset,
  limit,
  onOffsetChange,
}: {
  total: number
  offset: number
  limit: number
  onOffsetChange: (offset: number) => void
}) {
  if (total <= limit) return null
  const page = Math.floor(offset / limit) + 1
  const pageCount = Math.ceil(total / limit)
  const first = offset + 1
  const last = Math.min(offset + limit, total)

  return (
    <div className="flex flex-col items-center justify-between gap-3 sm:flex-row">
      <div className="text-xs text-muted-foreground">
        Showing {first.toLocaleString()}–{last.toLocaleString()} of {total.toLocaleString()}
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-label="Previous page"
          disabled={page === 1}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
          className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronLeft size={14} /> Previous
        </button>
        <span className="min-w-24 text-center text-xs text-muted-foreground">
          Page {page.toLocaleString()} of {pageCount.toLocaleString()}
        </span>
        <button
          type="button"
          aria-label="Next page"
          disabled={page === pageCount}
          onClick={() => onOffsetChange(offset + limit)}
          className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-40"
        >
          Next <ChevronRight size={14} />
        </button>
      </div>
    </div>
  )
}
