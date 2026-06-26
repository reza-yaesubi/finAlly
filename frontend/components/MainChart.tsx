"use client";

import { useEffect, useRef } from "react";
import { useApp } from "@/lib/AppContext";
import type { IChartApi, ISeriesApi, UTCTimestamp } from "lightweight-charts";

export default function MainChart() {
  const { selectedTicker, prices, priceHistory } = useApp();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const lastLengthRef = useRef<number>(0);

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return;

    let destroyed = false;
    let resizeObserver: ResizeObserver | null = null;

    import("lightweight-charts").then(({ createChart, ColorType, LineSeries }) => {
      if (destroyed || !containerRef.current) return;

      const chart = createChart(containerRef.current, {
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight,
        layout: {
          background: { type: ColorType.Solid, color: "#161b22" },
          textColor: "#8b949e",
        },
        grid: {
          vertLines: { color: "#21262d" },
          horzLines: { color: "#21262d" },
        },
        crosshair: {
          vertLine: { color: "#30363d" },
          horzLine: { color: "#30363d" },
        },
        rightPriceScale: {
          borderColor: "#30363d",
        },
        timeScale: {
          borderColor: "#30363d",
          timeVisible: true,
          secondsVisible: true,
        },
      });

      const series = chart.addSeries(LineSeries, {
        color: "#ecad0a",
        lineWidth: 2,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
        crosshairMarkerBorderColor: "#ecad0a",
        crosshairMarkerBackgroundColor: "#ecad0a",
        priceLineVisible: false,
      });

      chartRef.current = chart;
      seriesRef.current = series;
      lastLengthRef.current = 0;

      resizeObserver = new ResizeObserver(() => {
        if (containerRef.current && chartRef.current) {
          chartRef.current.applyOptions({
            width: containerRef.current.clientWidth,
            height: containerRef.current.clientHeight,
          });
        }
      });
      resizeObserver.observe(containerRef.current);
    });

    return () => {
      destroyed = true;
      resizeObserver?.disconnect();
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        seriesRef.current = null;
      }
    };
  }, []);

  // Reset series when ticker changes
  useEffect(() => {
    if (seriesRef.current) {
      seriesRef.current.setData([]);
      lastLengthRef.current = 0;
    }
  }, [selectedTicker]);

  // Update chart data when priceHistory changes
  useEffect(() => {
    if (!seriesRef.current || !selectedTicker) return;

    const history = priceHistory.get(selectedTicker) ?? [];
    if (history.length === 0) return;
    if (history.length === lastLengthRef.current) return;

    const now = Math.floor(Date.now() / 1000);
    const intervalSec = 0.5;

    const points = history.map((price, i) => ({
      time: Math.floor(now - (history.length - 1 - i) * intervalSec) as UTCTimestamp,
      value: price,
    }));

    // Deduplicate by time (take last value for each time key)
    const seen = new Map<number, number>();
    for (const p of points) {
      seen.set(p.time as number, p.value);
    }
    const deduped = Array.from(seen.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([time, value]) => ({ time: time as UTCTimestamp, value }));

    try {
      seriesRef.current.setData(deduped);
      lastLengthRef.current = history.length;
      chartRef.current?.timeScale().scrollToRealTime();
    } catch {
      // skip on error
    }
  }, [priceHistory, selectedTicker]);

  const priceData = selectedTicker ? prices.get(selectedTicker) : null;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        background: "#161b22",
        height: "100%",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "6px 12px",
          borderBottom: "1px solid #30363d",
          display: "flex",
          alignItems: "center",
          gap: 16,
          flexShrink: 0,
        }}
      >
        <span style={{ color: "#ecad0a", fontWeight: 700, fontSize: 16 }}>
          {selectedTicker || "—"}
        </span>
        {priceData && (
          <>
            <span
              style={{
                color:
                  priceData.direction === "up"
                    ? "#3fb950"
                    : priceData.direction === "down"
                    ? "#f85149"
                    : "#e6edf3",
                fontSize: 20,
                fontWeight: 700,
              }}
            >
              ${priceData.price.toFixed(2)}
            </span>
            <span
              style={{
                color:
                  priceData.direction === "up"
                    ? "#3fb950"
                    : priceData.direction === "down"
                    ? "#f85149"
                    : "#8b949e",
                fontSize: 13,
              }}
            >
              {priceData.direction === "up"
                ? "+"
                : priceData.direction === "down"
                ? "-"
                : ""}
              {Math.abs(priceData.price - priceData.prev_price).toFixed(2)}
            </span>
          </>
        )}
        {!selectedTicker && (
          <span style={{ color: "#8b949e", fontSize: 13 }}>
            Select a ticker from the watchlist
          </span>
        )}
      </div>
      <div ref={containerRef} style={{ flex: 1, position: "relative" }} />
    </div>
  );
}
