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

interface BreadthChartProps {
  breadth: Record<string, number>; // ISO date → [0, 1]
  height?: number;
}

export function BreadthChart({ breadth, height = 180 }: BreadthChartProps) {
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
      rightPriceScale: {
        borderColor: "#334155",
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: { borderColor: "#334155" },
      height,
      width: containerRef.current.clientWidth,
    });

    chartRef.current = chart;

    const line = chart.addSeries(LineSeries, {
      color: "#10b981",
      lineWidth: 2,
      lineStyle: LineStyle.Solid,
      title: "Breadth",
    });

    const sorted: LineData[] = Object.entries(breadth)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([time, value]) => ({ time, value } as LineData));

    line.setData(sorted);
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
  }, [breadth, height]);

  return <div ref={containerRef} className="w-full" style={{ height }} />;
}
