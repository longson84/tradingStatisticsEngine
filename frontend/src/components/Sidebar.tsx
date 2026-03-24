import { NavLink } from "react-router"
import { BarChart2, TrendingUp, Layers, SlidersHorizontal } from "lucide-react"
import { cn } from "@/lib/utils"
import { ThemeToggle } from "@/components/theme-toggle"

const links = [
  { to: "/factors",  label: "Factor Analysis",   icon: BarChart2 },
  { to: "/backtest", label: "Strategy Backtest",  icon: TrendingUp },
  { to: "/batch",    label: "Batch Backtest",     icon: Layers },
  { to: "/sweep",    label: "Parameter Sweep",    icon: SlidersHorizontal },
]

export function Sidebar({ children, className }: { children?: React.ReactNode; className?: string }) {
  return (
    <aside className={cn("w-64 shrink-0 flex flex-col bg-card border-r border-border min-h-screen", className)}>
      <div className="px-4 py-5 border-b border-border flex items-center justify-between">
        <span className="text-sm font-semibold text-card-foreground tracking-wide">TSE</span>
        <ThemeToggle />
      </div>

      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
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
      </nav>

      {children && (
        <div className="border-t border-border p-4 space-y-4">
          {children}
        </div>
      )}
    </aside>
  )
}
