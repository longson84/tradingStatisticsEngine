import { BrowserRouter, Routes, Route, Navigate } from "react-router"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { FactorsPage } from "@/pages/FactorsPage"

const qc = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/factors" replace />} />
          <Route path="/factors" element={<FactorsPage />} />
          <Route path="/backtest" element={<Placeholder title="Strategy Backtest" />} />
          <Route path="/batch" element={<Placeholder title="Batch Backtest" />} />
          <Route path="/sweep" element={<Placeholder title="Parameter Sweep" />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

function Placeholder({ title }: { title: string }) {
  return (
    <div className="flex items-center justify-center h-screen text-white/40 text-sm">
      {title} — coming soon
    </div>
  )
}
