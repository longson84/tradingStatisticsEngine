"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { EquityChart } from "@/components/charts/EquityChart";
import { api, type SweepRequest, type StrategyConfig } from "@/lib/api";

const DEFAULT_STRATEGIES: StrategyConfig[] = [
  { type: "buy_and_hold", weight: 1.0 },
  { type: "ma_crossover", fast_period: 10, slow_period: 50, ma_type: "sma" },
  { type: "ma_crossover", fast_period: 20, slow_period: 100, ma_type: "ema" },
];

export default function SweepPage() {
  const [symbolInput, setSymbolInput] = useState("AAPL");
  const [start, setStart] = useState("2022-01-01");
  const [end, setEnd] = useState("2024-12-31");
  const [initialCapital, setInitialCapital] = useState(10000);

  const mutation = useMutation({ mutationFn: api.sweep });

  function handleRun() {
    const req: SweepRequest = {
      symbols: symbolInput.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean),
      date_range: { start, end },
      strategies: DEFAULT_STRATEGIES,
      initial_capital: initialCapital,
    };
    mutation.mutate(req);
  }

  const result = mutation.data;
  const chartSeries = result?.results.map((r, i) => ({
    label: `${r.strategy_type} #${i + 1}`,
    data: r.equity_curve,
  })) ?? [];

  return (
    <div className="max-w-5xl space-y-6">
      <h1 className="text-2xl font-bold">Strategy Sweep</h1>
      <p className="text-sm text-muted-foreground">
        Runs Buy&amp;Hold vs MA Crossover (10/50 SMA) vs MA Crossover (20/100 EMA) side-by-side.
      </p>

      <Card>
        <CardContent className="pt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="space-y-1">
              <Label>Symbols</Label>
              <Input
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value)}
                placeholder="AAPL, MSFT"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label>Start</Label>
                <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label>End</Label>
                <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
              </div>
            </div>
            <div className="space-y-1">
              <Label>Initial capital</Label>
              <Input
                type="number"
                value={initialCapital}
                onChange={(e) => setInitialCapital(Number(e.target.value))}
              />
            </div>
          </div>
          <div className="flex items-end">
            <Button className="w-full" onClick={handleRun} disabled={mutation.isPending}>
              {mutation.isPending ? "Running…" : "Run Sweep"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {mutation.isError && (
        <p className="text-sm text-red-400">{String(mutation.error)}</p>
      )}

      {result && (
        <>
          {/* Comparison table */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {result.results.map((r, i) => (
              <Card key={i}>
                <CardHeader className="pb-1">
                  <CardTitle className="text-sm">{r.strategy_type}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1">
                  <p className={`text-xl font-bold ${r.total_return_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {r.total_return_pct >= 0 ? "+" : ""}{r.total_return_pct.toFixed(2)}%
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Final: ${r.final_nav.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </p>
                  <p className="text-xs text-muted-foreground">{r.trade_count} trades</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {result.errors.length > 0 && (
            <div className="space-y-1">
              {result.errors.map((e, i) => (
                <Badge key={i} variant="destructive">{e.strategy_type}: {e.error}</Badge>
              ))}
            </div>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Equity Curves</CardTitle>
            </CardHeader>
            <CardContent>
              <EquityChart series={chartSeries} height={360} />
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
