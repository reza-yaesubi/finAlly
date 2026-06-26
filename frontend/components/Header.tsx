"use client";

import { useApp } from "@/lib/AppContext";

function fmt(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

function ConnectionDot({ status }: { status: string }) {
  const color =
    status === "connected"
      ? "#3fb950"
      : status === "reconnecting"
      ? "#ecad0a"
      : "#f85149";

  return (
    <span
      title={status}
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: color,
        boxShadow: `0 0 6px ${color}`,
      }}
    />
  );
}

export default function Header() {
  const { portfolio, connectionStatus } = useApp();

  return (
    <header
      style={{
        background: "#161b22",
        borderBottom: "1px solid #30363d",
        padding: "0 16px",
        height: 44,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexShrink: 0,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            color: "#ecad0a",
            fontWeight: 700,
            fontSize: 18,
            letterSpacing: 1,
          }}
        >
          FIN
        </span>
        <span style={{ color: "#8b949e", fontWeight: 400, fontSize: 18 }}>
          ALLY
        </span>
        <span
          style={{
            color: "#8b949e",
            fontSize: 11,
            marginLeft: 4,
            letterSpacing: 2,
          }}
        >
          TRADING WORKSTATION
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
        {portfolio && (
          <>
            <div style={{ textAlign: "right" }}>
              <div style={{ color: "#8b949e", fontSize: 10 }}>TOTAL VALUE</div>
              <div
                style={{
                  color: "#ecad0a",
                  fontSize: 16,
                  fontWeight: 700,
                }}
              >
                {fmt(portfolio.total_value)}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ color: "#8b949e", fontSize: 10 }}>CASH</div>
              <div style={{ color: "#e6edf3", fontSize: 14 }}>
                {fmt(portfolio.cash)}
              </div>
            </div>
          </>
        )}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <ConnectionDot status={connectionStatus} />
          <span style={{ color: "#8b949e", fontSize: 11 }}>
            {connectionStatus.toUpperCase()}
          </span>
        </div>
      </div>
    </header>
  );
}
