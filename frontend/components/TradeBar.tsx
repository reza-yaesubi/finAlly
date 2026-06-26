"use client";

import { useState } from "react";
import { useApp } from "@/lib/AppContext";
import { executeTrade } from "@/lib/api";

export default function TradeBar() {
  const { selectedTicker, refreshPortfolio, refreshHistory } = useApp();
  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);
  const [loading, setLoading] = useState(false);

  const effectiveTicker = ticker.trim().toUpperCase() || selectedTicker;

  async function handleTrade(side: "buy" | "sell") {
    const qty = parseFloat(quantity);
    if (!effectiveTicker || isNaN(qty) || qty <= 0) {
      setMessage({ text: "Enter a valid ticker and quantity", ok: false });
      return;
    }
    setLoading(true);
    setMessage(null);
    try {
      const result = await executeTrade(effectiveTicker, qty, side);
      if (result.ok) {
        setMessage({
          text: `${side === "buy" ? "Bought" : "Sold"} ${qty} ${effectiveTicker} @ $${result.price?.toFixed(2)}`,
          ok: true,
        });
        setQuantity("");
        await Promise.all([refreshPortfolio(), refreshHistory()]);
      } else {
        setMessage({ text: result.error ?? "Trade failed", ok: false });
      }
    } catch {
      setMessage({ text: "Trade request failed", ok: false });
    } finally {
      setLoading(false);
      setTimeout(() => setMessage(null), 3000);
    }
  }

  const inputStyle = {
    background: "#0d1117",
    border: "1px solid #30363d",
    color: "#e6edf3",
    padding: "5px 8px",
    fontSize: 13,
    borderRadius: 4,
    outline: "none",
    width: "100%",
  };

  return (
    <div
      style={{
        background: "#161b22",
        borderTop: "1px solid #30363d",
        padding: "8px 10px",
        display: "flex",
        flexDirection: "column",
        gap: 6,
        flexShrink: 0,
      }}
    >
      <div style={{ color: "#8b949e", fontSize: 10, letterSpacing: 1 }}>
        TRADE
      </div>

      {message && (
        <div
          style={{
            color: message.ok ? "#3fb950" : "#f85149",
            fontSize: 11,
            padding: "2px 0",
          }}
        >
          {message.text}
        </div>
      )}

      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
        <input
          type="text"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder={selectedTicker || "TICKER"}
          style={{ ...inputStyle, width: 70 }}
        />
        <input
          type="number"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          placeholder="Qty"
          min={0}
          step="any"
          style={{ ...inputStyle, width: 70 }}
        />
        <button
          onClick={() => handleTrade("buy")}
          disabled={loading}
          style={{
            background: "#209dd7",
            border: "none",
            color: "#fff",
            padding: "5px 14px",
            fontSize: 12,
            borderRadius: 4,
            cursor: loading ? "not-allowed" : "pointer",
            fontWeight: 700,
            opacity: loading ? 0.7 : 1,
          }}
        >
          BUY
        </button>
        <button
          onClick={() => handleTrade("sell")}
          disabled={loading}
          style={{
            background: "#753991",
            border: "none",
            color: "#fff",
            padding: "5px 12px",
            fontSize: 12,
            borderRadius: 4,
            cursor: loading ? "not-allowed" : "pointer",
            fontWeight: 700,
            opacity: loading ? 0.7 : 1,
          }}
        >
          SELL
        </button>
      </div>

      {loading && (
        <div style={{ color: "#8b949e", fontSize: 10 }}>Executing...</div>
      )}
    </div>
  );
}
