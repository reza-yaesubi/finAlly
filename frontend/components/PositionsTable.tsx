"use client";

import { useApp } from "@/lib/AppContext";

function fmtCurrency(n: number) {
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

function fmtPct(n: number) {
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

export default function PositionsTable() {
  const { portfolio } = useApp();

  const activePositions = portfolio?.positions.filter((p) => p.quantity > 0) ?? [];

  if (activePositions.length === 0) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span style={{ color: "#8b949e", fontSize: 12 }}>No positions</span>
      </div>
    );
  }

  const headers = ["TICKER", "QTY", "AVG COST", "CURR PRICE", "P&L", "P&L %"];

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr>
            {headers.map((h) => (
              <th
                key={h}
                style={{
                  padding: "4px 8px",
                  color: "#8b949e",
                  fontWeight: 500,
                  fontSize: 10,
                  textAlign: h === "TICKER" ? "left" : "right",
                  borderBottom: "1px solid #30363d",
                  position: "sticky",
                  top: 0,
                  background: "#161b22",
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {activePositions.map((p) => {
            const pnlColor = p.unrealized_pnl >= 0 ? "#3fb950" : "#f85149";
            return (
              <tr
                key={p.ticker}
                style={{ borderBottom: "1px solid #21262d" }}
              >
                <td
                  style={{
                    padding: "5px 8px",
                    color: "#ecad0a",
                    fontWeight: 700,
                  }}
                >
                  {p.ticker}
                </td>
                <td
                  style={{
                    padding: "5px 8px",
                    color: "#e6edf3",
                    textAlign: "right",
                  }}
                >
                  {p.quantity.toFixed(2)}
                </td>
                <td
                  style={{
                    padding: "5px 8px",
                    color: "#8b949e",
                    textAlign: "right",
                  }}
                >
                  {fmtCurrency(p.avg_cost)}
                </td>
                <td
                  style={{
                    padding: "5px 8px",
                    color: "#e6edf3",
                    textAlign: "right",
                  }}
                >
                  {fmtCurrency(p.current_price)}
                </td>
                <td
                  style={{
                    padding: "5px 8px",
                    color: pnlColor,
                    textAlign: "right",
                    fontWeight: 600,
                  }}
                >
                  {fmtCurrency(p.unrealized_pnl)}
                </td>
                <td
                  style={{
                    padding: "5px 8px",
                    color: pnlColor,
                    textAlign: "right",
                  }}
                >
                  {fmtPct(p.pnl_pct)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
