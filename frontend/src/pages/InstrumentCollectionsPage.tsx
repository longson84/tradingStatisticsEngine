import { ListChecks, ListTree } from "lucide-react"
import { NavLink } from "react-router"

import { Sidebar } from "@/components/Sidebar"
import { UniversesPanel } from "@/pages/UniversesPage"
import { WatchlistsPanel } from "@/pages/WatchlistsPage"
import { cn } from "@/lib/utils"


type CollectionTab = "universes" | "watchlists"


export function InstrumentCollectionsPage({ tab }: { tab: CollectionTab }) {
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-y-auto p-6">
        <div className="mb-5 border-b border-border pb-4">
          <h1 className="text-2xl font-bold tracking-tight">Instrument Collections</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Universes are synchronized system collections; watchlists are ordered personal selections.
          </p>
          <nav className="mt-5 flex gap-2" aria-label="Instrument collection type">
            <CollectionTabLink
              to="/collections/universes"
              label="Universes"
              icon={ListTree}
            />
            <CollectionTabLink
              to="/collections/watchlists"
              label="Watchlists"
              icon={ListChecks}
            />
          </nav>
        </div>

        {tab === "universes" ? <UniversesPanel /> : <WatchlistsPanel />}
      </main>
    </div>
  )
}


function CollectionTabLink({
  to,
  label,
  icon: Icon,
}: {
  to: string
  label: string
  icon: React.ComponentType<{ size?: number }>
}) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) => cn(
        "inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium transition-colors",
        isActive
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-foreground",
      )}
    >
      <Icon size={15} />
      {label}
    </NavLink>
  )
}
