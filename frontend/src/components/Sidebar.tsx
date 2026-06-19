import { useState } from "react"
import { NavLink } from "react-router"
import { Activity, BarChart2, TrendingUp, ChevronUp, ChevronDown, Waves, SearchCode, Database } from "lucide-react"
import { cn } from "@/lib/utils"
import { ThemeToggle } from "@/components/theme-toggle"

const sections = [
  {
    label: "Factor Analysis",
    links: [
      { to: "/factor-rarity", label: "Factor Rarity", icon: BarChart2 },
    ],
  },
  {
    label: "Event Analysis",
    links: [
      { to: "/events/new-low", label: "New-Low Compare", icon: Waves, end: true },
      { to: "/events/new-low/deep", label: "New-Low Deep", icon: SearchCode },
    ],
  },
  {
    label: "Company Analysis",
    links: [
      { to: "/fundamentals", label: "Fundamentals", icon: Database },
      { to: "/company/growth", label: "Growth Dashboard", icon: Activity },
    ],
  },
  {
    label: "Strategy Analysis",
    links: [
      { to: "/strategy/sma", label: "SMA Strategy", icon: TrendingUp },
    ],
  },
]

export function Sidebar({ children, className }: { children?: React.ReactNode; className?: string }) {
  const [panelOpen, setPanelOpen] = useState(true)

  return (
    <aside className={cn("w-64 shrink-0 flex flex-col bg-card border-r border-border min-h-screen", className)}>
      <div className="px-4 py-5 border-b border-border flex items-center justify-between">
        <span className="text-sm font-semibold text-card-foreground tracking-wide">TSE</span>
        <ThemeToggle />
      </div>

      <nav className="px-2 py-3 space-y-3">
        {sections.map(section => (
          <div key={section.label}>
            <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
              {section.label}
            </div>
            <div className="space-y-0.5">
              {section.links.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-2.5 px-3 py-2 rounded text-sm transition-colors",
                      isActive
                        ? "bg-primary text-primary-foreground font-medium"
                        : "text-muted-foreground hover:text-foreground hover:bg-accent"
                    )
                  }
                >
                  <Icon size={15} />
                  {label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {children && (
        <>
          <button
            onClick={() => setPanelOpen(o => !o)}
            className="flex items-center justify-between px-4 py-2 border-t border-border text-[10px] uppercase tracking-widest text-muted-foreground hover:bg-accent/40 transition-colors"
          >
            <span>Controls</span>
            {panelOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>

          {panelOpen && (
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {children}
            </div>
          )}
        </>
      )}
    </aside>
  )
}
