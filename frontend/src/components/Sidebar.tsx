import { NavLink } from "react-router"
import { BarChart2, TrendingUp, Layers, SlidersHorizontal } from "lucide-react"
import { cn } from "@/lib/utils"

const links = [
  { to: "/factors",  label: "Factor Analysis",   icon: BarChart2 },
  { to: "/backtest", label: "Strategy Backtest",  icon: TrendingUp },
  { to: "/batch",    label: "Batch Backtest",     icon: Layers },
  { to: "/sweep",    label: "Parameter Sweep",    icon: SlidersHorizontal },
]

export function Sidebar({ children, className }: { children?: React.ReactNode; className?: string }) {
  return (
    <aside className={cn("w-64 shrink-0 flex flex-col bg-[#1a1b1e] border-r border-white/8 min-h-screen", className)}>
      <div className="px-4 py-5 border-b border-white/8">
        <span className="text-sm font-semibold text-white/90 tracking-wide">TSE</span>
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
                  ? "bg-white/10 text-white font-medium"
                  : "text-white/50 hover:text-white/80 hover:bg-white/5"
              )
            }
          >
            <Icon size={15} />
            {label}
          </NavLink>
        ))}
      </nav>

      {children && (
        <div className="border-t border-white/8 p-4 space-y-4">
          {children}
        </div>
      )}
    </aside>
  )
}
