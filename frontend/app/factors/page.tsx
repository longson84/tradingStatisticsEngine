"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BreadthChart } from "@/components/charts/BreadthChart";
import {
  api,
  type FactorRequest,
  type CrossSectionalRequest,
  type FactorType,
  type MaType,
} from "@/lib/api";

export default function FactorsPage() {
  // ── Time-series (single symbol) ──────────────────────────────────────────
  const [tsReq, setTsReq] = useState<FactorRequest>({
    symbol: "AAPL",
    date_range: { start: "2020-01-01", end: "2024-12-31" },
    factor_type: "moving_average",
    period: 20,
    ma_type: "sma",
    data_source: "yfinance",
  });
  const tsMutation = useMutation({ mutationFn: api.analyzeFactor });

  // ── Cross-sectional (universe) ───────────────────────────────────────────
  const [csSymbols, setCsSymbols] = useState("AAPL,MSFT,GOOGL,AMZN,META");
  const [csReq, setCsReq] = useState<Omit<CrossSectionalRequest, "symbols">>({
    date_range: { start: "2022-01-01", end: "2024-12-31" },
    factor_type: "moving_average",
    period: 20,
    ma_type: "sma",
    threshold: 0,
    data_source: "yfinance",
  });
  const csMutation = useMutation({ mutationFn: api.analyzeUniverse });

  function runTs() {
    tsMutation.mutate(tsReq);
  }

  function runCs() {
    csMutation.mutate({
      ...csReq,
      symbols: csSymbols.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean),
    });
  }

  const tsResult = tsMutation.data;
  const csResult = csMutation.data;

  const PERCENTILE_ORDER = ["p10", "p25", "p50", "p75", "p90"];

  return (
    <div className="max-w-5xl space-y-6">
      <h1 className="text-2xl font-bold">Factors</h1>

      <Tabs defaultValue="timeseries">
        <TabsList>
          <TabsTrigger value="timeseries">Time-Series (1 symbol)</TabsTrigger>
          <TabsTrigger value="universe">Universe Breadth</TabsTrigger>
        </TabsList>

        {/* ── Time-series tab ────────────────────────────────────────────── */}
        <TabsContent value="timeseries" className="space-y-4">
          <Card>
            <CardContent className="pt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-3">
                <div className="space-y-1">
                  <Label>Symbol</Label>
                  <Input
                    value={tsReq.symbol}
                    onChange={(e) => setTsReq((r) => ({ ...r, symbol: e.target.value.toUpperCase() }))}
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <Label>Start</Label>
                    <Input
                      type="date"
                      value={tsReq.date_range.start}
                      onChange={(e) =>
                        setTsReq((r) => ({ ...r, date_range: { ...r.date_range, start: e.target.value } }))
                      }
                    />
                  </div>
                  <div className="space-y-1">
                    <Label>End</Label>
                    <Input
                      type="date"
                      value={tsReq.date_range.end}
                      onChange={(e) =>
                        setTsReq((r) => ({ ...r, date_range: { ...r.date_range, end: e.target.value } }))
                      }
                    />
                  </div>
                </div>
              </div>
              <div className="space-y-3">
                <div className="space-y-1">
                  <Label>Factor</Label>
                  <Select
                    value={tsReq.factor_type}
                    onValueChange={(v) => setTsReq((r) => ({ ...r, factor_type: v as FactorType }))}
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="moving_average">Moving Average Ratio</SelectItem>
                      <SelectItem value="bollinger">Bollinger Position</SelectItem>
                      <SelectItem value="donchian">Donchian Channel</SelectItem>
                      <SelectItem value="distance_from_peak">Distance From Peak</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <Label>Period</Label>
                    <Input
                      type="number"
                      value={tsReq.period}
                      onChange={(e) => setTsReq((r) => ({ ...r, period: Number(e.target.value) }))}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label>MA type</Label>
                    <Select
                      value={tsReq.ma_type}
                      onValueChange={(v) => setTsReq((r) => ({ ...r, ma_type: v as MaType }))}
                    >
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="sma">SMA</SelectItem>
                        <SelectItem value="ema">EMA</SelectItem>
                        <SelectItem value="wma">WMA</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <Button className="w-full" onClick={runTs} disabled={tsMutation.isPending}>
                  {tsMutation.isPending ? "Computing…" : "Analyze"}
                </Button>
              </div>
            </CardContent>
          </Card>

          {tsMutation.isError && (
            <p className="text-sm text-red-400">{String(tsMutation.error)}</p>
          )}

          {tsResult && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card className="md:col-span-2">
                <CardHeader className="pb-1">
                  <CardTitle className="text-sm text-muted-foreground">Current Value</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">{tsResult.current_value.toFixed(4)}</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    {tsResult.current_percentile.toFixed(1)}th percentile over {tsResult.history_length_days} days
                  </p>
                </CardContent>
              </Card>

              {PERCENTILE_ORDER.filter((k) => k in tsResult.percentiles).map((key) => (
                <Card key={key}>
                  <CardHeader className="pb-1">
                    <CardTitle className="text-sm text-muted-foreground">{key.toUpperCase()}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-lg font-semibold">{tsResult.percentiles[key].toFixed(4)}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* ── Universe breadth tab ───────────────────────────────────────── */}
        <TabsContent value="universe" className="space-y-4">
          <Card>
            <CardContent className="pt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-3">
                <div className="space-y-1">
                  <Label>Symbols (comma-separated)</Label>
                  <Input
                    value={csSymbols}
                    onChange={(e) => setCsSymbols(e.target.value)}
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <Label>Start</Label>
                    <Input
                      type="date"
                      value={csReq.date_range.start}
                      onChange={(e) =>
                        setCsReq((r) => ({ ...r, date_range: { ...r.date_range, start: e.target.value } }))
                      }
                    />
                  </div>
                  <div className="space-y-1">
                    <Label>End</Label>
                    <Input
                      type="date"
                      value={csReq.date_range.end}
                      onChange={(e) =>
                        setCsReq((r) => ({ ...r, date_range: { ...r.date_range, end: e.target.value } }))
                      }
                    />
                  </div>
                </div>
              </div>
              <div className="space-y-3">
                <div className="space-y-1">
                  <Label>Factor</Label>
                  <Select
                    value={csReq.factor_type}
                    onValueChange={(v) => setCsReq((r) => ({ ...r, factor_type: v as FactorType }))}
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="moving_average">Moving Average Ratio</SelectItem>
                      <SelectItem value="bollinger">Bollinger Position</SelectItem>
                      <SelectItem value="donchian">Donchian Channel</SelectItem>
                      <SelectItem value="distance_from_peak">Distance From Peak</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <Label>Period</Label>
                    <Input
                      type="number"
                      value={csReq.period}
                      onChange={(e) => setCsReq((r) => ({ ...r, period: Number(e.target.value) }))}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label>Threshold</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={csReq.threshold}
                      onChange={(e) => setCsReq((r) => ({ ...r, threshold: Number(e.target.value) }))}
                    />
                  </div>
                </div>
                <Button className="w-full" onClick={runCs} disabled={csMutation.isPending}>
                  {csMutation.isPending ? "Computing…" : "Analyze Universe"}
                </Button>
              </div>
            </CardContent>
          </Card>

          {csMutation.isError && (
            <p className="text-sm text-red-400">{String(csMutation.error)}</p>
          )}

          {csResult && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">
                    {csResult.factor_name} — {csResult.universe.length} symbols
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <BreadthChart breadth={csResult.breadth} />
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
