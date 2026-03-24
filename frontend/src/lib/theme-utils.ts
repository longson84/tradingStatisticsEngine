export type Theme = "dark" | "light" | "system"

export function getSystemTheme(): "dark" | "light" {
  if (typeof window === "undefined") return "light"
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export function getInitialTheme(): Theme {
  if (typeof window === "undefined") return "system"
  return (localStorage.getItem("theme") as Theme) || "system"
}