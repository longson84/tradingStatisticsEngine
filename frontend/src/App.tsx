import { BrowserRouter, Routes, Route, Navigate } from "react-router"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { FactorsPage } from "@/pages/FactorsPage"
import { SmaStrategyPage } from "@/pages/SmaStrategyPage"
import { NewLowComparisonPage } from "@/pages/NewLowComparisonPage"
import { NewLowDeepPage } from "@/pages/NewLowDeepPage"
import { FundamentalsPage } from "@/pages/FundamentalsPage"
import { GrowthDashboardPage } from "@/pages/GrowthDashboardPage"

const qc = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10 * 60 * 1000,
      gcTime: 30 * 60 * 1000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
      refetchOnMount: false,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/factor-rarity" replace />} />
          <Route path="/factor-rarity" element={<FactorsPage />} />
          <Route path="/events/new-low" element={<NewLowComparisonPage />} />
          <Route path="/events/new-low/deep" element={<NewLowDeepPage />} />
          <Route path="/fundamentals" element={<FundamentalsPage />} />
          <Route path="/company/growth" element={<GrowthDashboardPage />} />
          <Route path="/strategy/sma" element={<SmaStrategyPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
