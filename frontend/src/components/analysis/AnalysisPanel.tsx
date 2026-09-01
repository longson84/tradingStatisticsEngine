import { ChevronLeft, ChevronRight, SlidersHorizontal } from "lucide-react"
import { useEffect, useState, type ReactNode } from "react"

import { cn } from "@/lib/utils"

const STORAGE_KEY = "tse.analysis-panel.collapsed"

export function AnalysisPanel({
  children,
  label = "Analysis controls",
}: {
  children: ReactNode
  label?: string
}) {
  const [collapsed, setCollapsed] = useState(() => (
    window.localStorage.getItem(STORAGE_KEY) === "true"
  ))

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, String(collapsed))
  }, [collapsed])

  return (
    <aside
      className={cn(
        "relative flex min-h-screen shrink-0 flex-col border-r border-border bg-card transition-[width] duration-200",
        collapsed ? "w-11" : "w-72",
      )}
    >
      <div className={cn(
        "flex h-[65px] shrink-0 items-center border-b border-border",
        collapsed ? "justify-center px-1" : "justify-between px-4",
      )}>
        {!collapsed && (
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            <SlidersHorizontal size={13} />
            {label}
          </div>
        )}
        <button
          type="button"
          onClick={() => setCollapsed(value => !value)}
          aria-label={collapsed ? "Expand analysis controls" : "Collapse analysis controls"}
          title={collapsed ? "Expand controls" : "Collapse controls"}
          className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {!collapsed && (
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {children}
        </div>
      )}

      {collapsed && (
        <div className="flex flex-1 justify-center pt-4">
          <SlidersHorizontal size={15} className="text-muted-foreground" />
        </div>
      )}
    </aside>
  )
}
