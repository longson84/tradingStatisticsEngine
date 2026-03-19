"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  LineSeries,
  LineStyle,
  type IChartApi,
  type LineData,
} from "lightweight-charts";

interface EquitySeries {
  label: string;
  data: Record<string, number>; // ISO date → NAV
  color?: string;
}

interface EquityChartProps {
  series: EquitySeries[];
  height?: number;
}

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

export function EquityChart({ series, height = 320 }: EquityChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: "#334155" },
      timeScale: { borderColor: "#334155", timeVisible: true },
      height,
      width: containerRef.current.clientWidth,
    });

    chartRef.current = chart;

    series.forEach((s, i) => {
      const line = chart.addSeries(LineSeries, {
        color: s.color ?? COLORS[i % COLORS.length],
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        title: s.label,
      });

      const sorted: LineData[] = Object.entries(s.data)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([time, value]) => ({ time, value } as LineData));

      line.setData(sorted);
    });

    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [series, height]);

  return <div ref={containerRef} className="w-full" style={{ height }} />;
}
