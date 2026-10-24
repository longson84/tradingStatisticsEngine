import { ColorType, createChart, HistogramSeries, LineSeries, type Time } from "lightweight-charts"
import { useEffect, useRef } from "react"

import type { InstrumentFlowPoint } from "@/lib/api"


export function InvestorFlowChart({ observations }: { observations: InstrumentFlowPoint[] }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container || observations.length === 0) return
    const chart = createChart(container, {
      width: container.clientWidth,
      height: 360,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#6b7280",
        fontFamily: "inherit",
      },
      grid: {
        vertLines: { color: "rgba(107, 114, 128, 0.14)" },
        horzLines: { color: "rgba(107, 114, 128, 0.14)" },
      },
      localization: { dateFormat: "dd/MM/yy" },
      timeScale: { borderColor: "#374151" },
      rightPriceScale: { borderColor: "#374151" },
    })
    const net = chart.addSeries(HistogramSeries, {
      title: "Net value",
      priceFormat: { type: "volume" },
      priceLineVisible: false,
      lastValueVisible: true,
    })
    net.setData(observations.map(point => ({
      time: point.date as Time,
      value: point.net_value,
      color: point.net_value >= 0 ? "rgba(22, 163, 74, 0.72)" : "rgba(220, 38, 38, 0.72)",
    })))
    net.createPriceLine({
      price: 0,
      color: "#6b7280",
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: true,
      title: "Zero",
    })
    const buy = chart.addSeries(LineSeries, {
      title: "Buy value",
      color: "#16a34a",
      lineWidth: 2,
      priceLineVisible: false,
    })
    buy.setData(observations.map(point => ({ time: point.date as Time, value: point.buy_value })))
    const sell = chart.addSeries(LineSeries, {
      title: "Sell value",
      color: "#dc2626",
      lineWidth: 2,
      priceLineVisible: false,
    })
    sell.setData(observations.map(point => ({ time: point.date as Time, value: point.sell_value })))
    chart.timeScale().fitContent()

    const resize = new ResizeObserver(entries => {
      const width = entries[0]?.contentRect.width
      if (width) chart.applyOptions({ width })
    })
    resize.observe(container)
    return () => {
      resize.disconnect()
      chart.remove()
    }
  }, [observations])

  return <div ref={containerRef} className="w-full" aria-label="Foreign investor flow chart" />
}
