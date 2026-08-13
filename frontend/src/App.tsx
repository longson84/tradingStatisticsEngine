import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { FactorsPage } from "@/pages/FactorsPage"
import { PredefinedFactorsRarityPage } from "@/pages/PredefinedFactorsRarityPage"
import { SmaStrategyPage } from "@/pages/SmaStrategyPage"
import { NewLowDeepPage } from "@/pages/NewLowDeepPage"
import { InstrumentsPage } from "@/pages/InstrumentsPage"
import { CompaniesPage } from "@/pages/CompaniesPage"
import { DataOperationsPage } from "@/pages/DataOperationsPage"
import { PriceHistoryPage } from "@/pages/PriceHistoryPage"
import { InstrumentCollectionsPage } from "@/pages/InstrumentCollectionsPage"
import { CryptoMarketsPage } from "@/pages/CryptoMarketsPage"
import { DataModelPage } from "@/pages/DataModelPage"
import { ReferenceRatesPage } from "@/pages/ReferenceRatesPage"
import { VenuesPage } from "@/pages/VenuesPage"
import { UniverseStatsPage } from "@/pages/UniverseStatsPage"

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
          <Route path="/factor-rarity/predefined" element={<PredefinedFactorsRarityPage />} />
          <Route path="/universe-stats" element={<UniverseStatsPage />} />
          <Route path="/events/new-low/deep" element={<NewLowDeepPage />} />
          <Route path="/instruments" element={<InstrumentsPage />} />
          <Route path="/companies" element={<CompaniesPage />} />
          <Route path="/company/lists" element={<LegacyInstrumentsRedirect />} />
          <Route path="/company/price-history" element={<PriceHistoryPage />} />
          <Route path="/collections" element={<Navigate to="/collections/universes" replace />} />
          <Route path="/collections/universes" element={<InstrumentCollectionsPage tab="universes" />} />
          <Route path="/collections/watchlists" element={<InstrumentCollectionsPage tab="watchlists" />} />
          <Route path="/company/watchlists" element={<LegacyWatchlistsRedirect />} />
          <Route path="/data-operations" element={<DataOperationsPage />} />
          <Route path="/crypto" element={<CryptoMarketsPage />} />
          <Route path="/reference-rates" element={<ReferenceRatesPage />} />
          <Route path="/build/data-model" element={<DataModelPage />} />
          <Route path="/venues" element={<VenuesPage />} />
          <Route path="/build/venues" element={<Navigate to="/venues" replace />} />
          <Route path="/strategy/sma" element={<SmaStrategyPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

function LegacyInstrumentsRedirect() {
  const location = useLocation()
  return <Navigate to={{ pathname: "/instruments", search: location.search }} replace />
}

function LegacyWatchlistsRedirect() {
  const location = useLocation()
  return <Navigate to={{ pathname: "/collections/watchlists", search: location.search }} replace />
}
