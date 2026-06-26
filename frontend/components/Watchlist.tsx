"use client";

import { useState, useRef, useEffect } from "react";
import { useApp } from "@/lib/AppContext";
import Sparkline from "./Sparkline";
import { addToWatchlist, removeFromWatchlist } from "@/lib/api";

function fmtPrice(n: number) {
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtPct(pct: number) {
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function useFlash(price: number) {
  const prevRef = useRef<number | null>(null);
  const [flash, setFlash] = useState<"up" | "down" | null>(null);

  useEffect(() => {
    if (prevRef.current !== null && prevRef.current !== price) {
      setFlash(price > prevRef.current ? "up" : "down");
      const timer = setTimeout(() => setFlash(null), 600);
      prevRef.current = price;
      return () => clearTimeout(timer);
    }
    prevRef.current = price;
  }, [price]);

  return flash;
}

interface TickerRowProps {
  ticker: string;
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
}

function TickerRow({ ticker, selected, onSelect, onRemove }: TickerRowProps) {
  const { prices, priceHistory } = useApp();
  const priceData = prices.get(ticker);
  const history = priceHistory.get(ticker) ?? [];
  const currentPrice = priceData?.price ?? 0;
  const flash = useFlash(currentPrice);

  const firstPrice = history[0] ?? currentPrice;
  const pctChange =
    firstPrice > 0 ? ((currentPrice - firstPrice) / firstPrice) * 100 : 0;
  const pctColor = pctChange >= 0 ? "#3fb950" : "#f85149";

  const sparkColor = pctChange >= 0 ? "#3fb950" : "#f85149";

  return (
    <div
      onClick={onSelect}
      className={flash === "up" ? "flash-up" : flash === "down" ? "flash-down" : ""}
      style={{
        display: "grid",
        gridTemplateColumns: "56px 70px 52px 84px 20px",
        alignItems: "center",
        gap: 4,
        padding: "6px 8px",
        cursor: "pointer",
        borderBottom: "1px solid #21262d",
        background: selected ? "#21262d" : "transparent",
        borderLeft: selected ? "2px solid #ecad0a" : "2px solid transparent",
        transition: "background 0.15s",
      }}
    >
      <span style={{ color: "#e6edf3", fontWeight: 600, fontSize: 12 }}>
        {ticker}
      </span>
      <span style={{ color: "#e6edf3", fontSize: 12, textAlign: "right" }}>
        {currentPrice > 0 ? fmtPrice(currentPrice) : "—"}
      </span>
      <span style={{ color: pctColor, fontSize: 11, textAlign: "right" }}>
        {currentPrice > 0 ? fmtPct(pctChange) : "—"}
      </span>
      <Sparkline data={history} width={80} height={24} color={sparkColor} />
      <button
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        title="Remove"
        style={{
          background: "none",
          border: "none",
          color: "#8b949e",
          cursor: "pointer",
          fontSize: 14,
          padding: 0,
          lineHeight: 1,
        }}
      >
        x
      </button>
    </div>
  );
}

export default function Watchlist() {
  const { watchlist, selectedTicker, setSelectedTicker, refreshWatchlist } =
    useApp();
  const [newTicker, setNewTicker] = useState("");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAdd() {
    const t = newTicker.trim().toUpperCase();
    if (!t) return;
    setAdding(true);
    setError(null);
    try {
      await addToWatchlist(t);
      setNewTicker("");
      await refreshWatchlist();
      setSelectedTicker(t);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add");
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(ticker: string) {
    try {
      await removeFromWatchlist(ticker);
      await refreshWatchlist();
      if (selectedTicker === ticker && watchlist.length > 1) {
        const next = watchlist.find((t) => t !== ticker);
        if (next) setSelectedTicker(next);
      }
    } catch {
      // ignore
    }
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "#161b22",
        borderRight: "1px solid #30363d",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "8px 10px 6px",
          borderBottom: "1px solid #30363d",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            color: "#8b949e",
            fontSize: 10,
            letterSpacing: 1,
            marginBottom: 4,
          }}
        >
          WATCHLIST
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "56px 70px 52px 84px 20px",
            gap: 4,
            padding: "0 8px",
          }}
        >
          {["TICKER", "PRICE", "CHG%", "TREND", ""].map((h) => (
            <span
              key={h}
              style={{
                color: "#8b949e",
                fontSize: 9,
                textAlign: h === "PRICE" || h === "CHG%" ? "right" : "left",
              }}
            >
              {h}
            </span>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto" }}>
        {watchlist.map((ticker) => (
          <TickerRow
            key={ticker}
            ticker={ticker}
            selected={selectedTicker === ticker}
            onSelect={() => setSelectedTicker(ticker)}
            onRemove={() => handleRemove(ticker)}
          />
        ))}
      </div>

      <div
        style={{
          padding: "8px",
          borderTop: "1px solid #30363d",
          flexShrink: 0,
        }}
      >
        {error && (
          <div style={{ color: "#f85149", fontSize: 10, marginBottom: 4 }}>
            {error}
          </div>
        )}
        <div style={{ display: "flex", gap: 4 }}>
          <input
            type="text"
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder="Add ticker..."
            style={{
              flex: 1,
              background: "#0d1117",
              border: "1px solid #30363d",
              color: "#e6edf3",
              padding: "4px 8px",
              fontSize: 12,
              borderRadius: 4,
              outline: "none",
            }}
          />
          <button
            onClick={handleAdd}
            disabled={adding}
            style={{
              background: "#209dd7",
              border: "none",
              color: "#fff",
              padding: "4px 10px",
              fontSize: 12,
              borderRadius: 4,
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}
