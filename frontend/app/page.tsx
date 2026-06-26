"use client";

import { AppProvider } from "@/lib/AppContext";
import Header from "@/components/Header";
import Watchlist from "@/components/Watchlist";
import MainChart from "@/components/MainChart";
import PortfolioHeatmap from "@/components/PortfolioHeatmap";
import PnLChart from "@/components/PnLChart";
import PositionsTable from "@/components/PositionsTable";
import TradeBar from "@/components/TradeBar";
import ChatPanel from "@/components/ChatPanel";

export default function Home() {
  return (
    <AppProvider>
      <TradingWorkstation />
    </AppProvider>
  );
}

function TradingWorkstation() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        background: "#0d1117",
        overflow: "hidden",
      }}
    >
      <Header />

      {/* Main 3-column layout */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "290px 1fr 300px",
          flex: 1,
          overflow: "hidden",
          minHeight: 0,
        }}
      >
        {/* Left column: Watchlist + TradeBar */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            borderRight: "1px solid #30363d",
          }}
        >
          <div style={{ flex: 1, overflow: "hidden" }}>
            <Watchlist />
          </div>
          <TradeBar />
        </div>

        {/* Center column */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          {/* Top: Main chart */}
          <div
            style={{
              flex: "0 0 45%",
              borderBottom: "1px solid #30363d",
              overflow: "hidden",
            }}
          >
            <MainChart />
          </div>

          {/* Middle: Portfolio heatmap */}
          <div
            style={{
              flex: "0 0 25%",
              borderBottom: "1px solid #30363d",
              overflow: "hidden",
              padding: "0",
            }}
          >
            <SectionLabel label="PORTFOLIO HEATMAP" />
            <div style={{ height: "calc(100% - 22px)" }}>
              <PortfolioHeatmap />
            </div>
          </div>

          {/* Bottom: P&L chart + Positions table */}
          <div
            style={{
              flex: 1,
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              overflow: "hidden",
              minHeight: 0,
            }}
          >
            <div
              style={{
                borderRight: "1px solid #30363d",
                overflow: "hidden",
                display: "flex",
                flexDirection: "column",
              }}
            >
              <SectionLabel label="P&L CHART" />
              <div style={{ flex: 1, minHeight: 0, padding: "4px 4px 4px 0" }}>
                <PnLChart />
              </div>
            </div>
            <div
              style={{
                overflow: "hidden",
                display: "flex",
                flexDirection: "column",
              }}
            >
              <SectionLabel label="POSITIONS" />
              <div style={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
                <PositionsTable />
              </div>
            </div>
          </div>
        </div>

        {/* Right column: AI Chat */}
        <div style={{ overflow: "hidden" }}>
          <ChatPanel />
        </div>
      </div>
    </div>
  );
}

function SectionLabel({ label }: { label: string }) {
  return (
    <div
      style={{
        padding: "3px 10px",
        color: "#8b949e",
        fontSize: 9,
        letterSpacing: 1,
        borderBottom: "1px solid #21262d",
        flexShrink: 0,
      }}
    >
      {label}
    </div>
  );
}
