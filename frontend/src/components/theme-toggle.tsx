import { Moon, Sun } from "lucide-react"
import { useTheme } from "@/lib/theme-context"
import { cn } from "@/lib/utils"

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { resolvedTheme, setTheme } = useTheme()
  const dark = resolvedTheme === "dark"

  return (
    <button
      type="button"
      role="switch"
      aria-checked={dark}
      aria-label={`Switch to ${dark ? "light" : "dark"} mode`}
      onClick={() => setTheme(dark ? "light" : "dark")}
      className={cn(
        "flex items-center justify-between gap-3 rounded-md text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
        compact ? "p-2" : "w-full px-3 py-2",
      )}
    >
      <span className={cn("items-center gap-2.5", compact ? "hidden" : "flex")}>
        {dark ? <Moon size={15} /> : <Sun size={15} />}
        {dark ? "Dark mode" : "Light mode"}
      </span>
      {compact && (dark ? <Moon size={15} /> : <Sun size={15} />)}
      <span
        aria-hidden="true"
        className={cn(
          "relative h-5 w-9 rounded-full border transition-colors",
          dark ? "border-primary bg-primary" : "border-border bg-muted",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-3.5 w-3.5 rounded-full bg-background shadow-sm transition-transform",
            dark ? "translate-x-[17px]" : "translate-x-0.5",
          )}
        />
      </span>
    </button>
  )
}
