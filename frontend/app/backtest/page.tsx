"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EquityChart } from "@/components/charts/EquityChart";
import { StrategyPicker } from "@/components/forms/StrategyPicker";
import { api, type BacktestRequest, type StrategyConfig, type Trade } from "@/lib/api";

const DEFAULT_REQ: BacktestRequest = {
  symbols: ["AAPL"],
  date_range: { start: "2022-01-01", end: "2024-12-31" },
  strategy: { type: "buy_and_hold", weight: 1.0 },
  initial_capital: 10000,
  max_leverage: 1.0,
  data_source: "yfinance",
};

function TradeRow({ trade }: { trade: Trade }) {
  const ret = trade.return_pct ?? 0;
  return (
    <tr className="border-b border-border text-sm">
      <td className="py-2 pr-4 font-medium">{trade.symbol}</td>
      <td className="py-2 pr-4">
        <Badge variant={trade.direction === "long" ? "default" : "secondary"}>
          {trade.direction}
        </Badge>
      </td>
      <td className="py-2 pr-4 text-muted-foreground">{trade.entry_date}</td>
      <td className="py-2 pr-4 text-muted-foreground">{trade.exit_date ?? "—"}</td>
      <td className="py-2 pr-4">{trade.holding_days ?? "—"}d</td>
      <td className={`py-2 font-medium ${ret >= 0 ? "text-emerald-400" : "text-red-400"}`}>
        {ret >= 0 ? "+" : ""}{ret.toFixed(2)}%
      </td>
    </tr>
  );
}

export default function BacktestPage() {
  const [req, setReq] = useState<BacktestRequest>(DEFAULT_REQ);
  const [symbolInput, setSymbolInput] = useState("AAPL");

  const mutation = useMutation({ mutationFn: api.backtest });

  function handleRun() {
    mutation.mutate({
      ...req,
      symbols: symbolInput.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean),
    });
  }

  const result = mutation.data;

  return (
    <div className="max-w-5xl space-y-6">
      <h1 className="text-2xl font-bold">Backtest</h1>

      {/* Config panel */}
      <Card>
        <CardContent className="pt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="space-y-1">
              <Label>Symbols (comma-separated)</Label>
              <Input
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value)}
                placeholder="AAPL, MSFT, TSLA"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label>Start date</Label>
                <Input
                  type="date"
                  value={req.date_range.start}
                  onChange={(e) =>
                    setReq((r) => ({ ...r, date_range: { ...r.date_range, start: e.target.value } }))
                  }
                />
              </div>
              <div className="space-y-1">
                <Label>End date</Label>
                <Input
                  type="date"
                  value={req.date_range.end}
                  onChange={(e) =>
                    setReq((r) => ({ ...r, date_range: { ...r.date_range, end: e.target.value } }))
                  }
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label>Initial capital</Label>
                <Input
                  type="number"
                  value={req.initial_capital}
                  onChange={(e) => setReq((r) => ({ ...r, initial_capital: Number(e.target.value) }))}
                />
              </div>
              <div className="space-y-1">
                <Label>Max leverage</Label>
                <Input
                  type="number"
                  step="0.1"
                  min="0.1"
                  value={req.max_leverage}
                  onChange={(e) => setReq((r) => ({ ...r, max_leverage: Number(e.target.value) }))}
                />
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <StrategyPicker
              value={req.strategy}
              onChange={(s: StrategyConfig) => setReq((r) => ({ ...r, strategy: s }))}
            />
            <Button
              className="w-full"
              onClick={handleRun}
              disabled={mutation.isPending}
            >
              {mutation.isPending ? "Running…" : "Run Backtest"}
            </Button>
            {mutation.isError && (
              <p className="text-sm text-red-400">{String(mutation.error)}</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {result && (
        <>
          {/* Stats row */}
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm text-muted-foreground">Total Return</CardTitle>
              </CardHeader>
              <CardContent>
                <p className={`text-2xl font-bold ${result.total_return_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {result.total_return_pct >= 0 ? "+" : ""}{result.total_return_pct.toFixed(2)}%
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm text-muted-foreground">Final NAV</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">${result.final_nav.toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm text-muted-foreground">Trades</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{result.trades.length}</p>
              </CardContent>
            </Card>
          </div>

          <Tabs defaultValue="equity">
            <TabsList>
              <TabsTrigger value="equity">Equity Curve</TabsTrigger>
              <TabsTrigger value="trades">Trades</TabsTrigger>
            </TabsList>

            <TabsContent value="equity">
              <Card>
                <CardContent className="pt-6">
                  <EquityChart
                    series={[{ label: "Portfolio", data: result.equity_curve }]}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="trades">
              <Card>
                <CardContent className="pt-6 overflow-x-auto">
                  {result.trades.length === 0 ? (
                    <p className="text-muted-foreground text-sm">No trades generated.</p>
                  ) : (
                    <table className="w-full">
                      <thead>
                        <tr className="text-xs text-muted-foreground border-b border-border">
                          <th className="text-left pb-2 pr-4">Symbol</th>
                          <th className="text-left pb-2 pr-4">Dir</th>
                          <th className="text-left pb-2 pr-4">Entry</th>
                          <th className="text-left pb-2 pr-4">Exit</th>
                          <th className="text-left pb-2 pr-4">Days</th>
                          <th className="text-left pb-2">Return</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.trades.map((t, i) => (
                          <TradeRow key={i} trade={t} />
                        ))}
                      </tbody>
                    </table>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
