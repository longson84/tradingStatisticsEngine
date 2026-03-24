import { Sun, Moon, Monitor } from "lucide-react"
import { useTheme } from "@/lib/theme"
import { Button } from "@/components/ui/button"

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  const getIcon = () => {
    switch (theme) {
      case "light":
        return <Sun className="h-4 w-4" />
      case "dark":
        return <Moon className="h-4 w-4" />
      default:
        return <Monitor className="h-4 w-4" />
    }
  }

  const cycleTheme = () => {
    const themes: Array<"light" | "dark" | "system"> = ["light", "dark", "system"]
    const currentIndex = themes.indexOf(theme)
    const nextIndex = (currentIndex + 1) % themes.length
    setTheme(themes[nextIndex])
  }

  return (
    <Button 
      variant="outline" 
      size="icon" 
      onClick={cycleTheme}
      title={`Current theme: ${theme}. Click to cycle through themes.`}
    >
      {getIcon()}
      <span className="sr-only">Toggle theme</span>
    </Button>
  )
}