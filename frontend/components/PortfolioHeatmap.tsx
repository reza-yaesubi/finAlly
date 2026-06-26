"use client";

import { Treemap, ResponsiveContainer, Tooltip } from "recharts";
import { useApp } from "@/lib/AppContext";

function getColor(pnlPct: number): string {
  const abs = Math.min(Math.abs(pnlPct), 10);
  const intensity = abs / 10;
  if (pnlPct >= 0) {
    const g = Math.round(80 + intensity * 105);
    return `rgb(0, ${g}, 60)`;
  } else {
    const r = Math.round(100 + intensity * 148);
    return `rgb(${r}, 30, 30)`;
  }
}

interface CustomContentProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  value?: number;
  pnl_pct?: number;
}

function CustomContent(props: CustomContentProps) {
  const { x = 0, y = 0, width = 0, height = 0, name, pnl_pct = 0 } = props;
  if (width < 20 || height < 20) return null;

  const bgColor = getColor(pnl_pct);
  const sign = pnl_pct >= 0 ? "+" : "";

  return (
    <g>
      <rect
        x={x + 1}
        y={y + 1}
        width={width - 2}
        height={height - 2}
        style={{ fill: bgColor, stroke: "#30363d", strokeWidth: 1 }}
        rx={2}
      />
      {height > 30 && (
        <text
          x={x + width / 2}
          y={y + height / 2 - 6}
          textAnchor="middle"
          fill="#e6edf3"
          fontSize={Math.min(14, width / 4)}
          fontWeight={700}
        >
          {name}
        </text>
      )}
      {height > 44 && (
        <text
          x={x + width / 2}
          y={y + height / 2 + 10}
          textAnchor="middle"
          fill={pnl_pct >= 0 ? "#3fb950" : "#f85149"}
          fontSize={Math.min(11, width / 5)}
        >
          {sign}{pnl_pct.toFixed(2)}%
        </text>
      )}
    </g>
  );
}

export default function PortfolioHeatmap() {
  const { portfolio } = useApp();

  const activePositions = portfolio?.positions.filter((p) => p.quantity > 0) ?? [];

  if (activePositions.length === 0) {
    return (
      <div
        style={{
          background: "#161b22",
          border: "1px solid #30363d",
          borderRadius: 4,
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span style={{ color: "#8b949e", fontSize: 13 }}>No positions yet</span>
      </div>
    );
  }

  const totalValue =
    portfolio?.total_value ?? activePositions.reduce((s, p) => s + p.quantity * p.current_price, 0);

  const data = activePositions.map((p) => ({
    name: p.ticker,
    value: Math.max(p.quantity * p.current_price, 0.01),
    pnl_pct: p.pnl_pct,
    size: ((p.quantity * p.current_price) / totalValue) * 100,
  }));

  return (
    <div
      style={{
        background: "#161b22",
        height: "100%",
        overflow: "hidden",
      }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <Treemap
          data={data}
          dataKey="value"
          aspectRatio={4 / 3}
          content={<CustomContent />}
        >
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload;
              return (
                <div
                  style={{
                    background: "#21262d",
                    border: "1px solid #30363d",
                    padding: "6px 10px",
                    fontSize: 12,
                    color: "#e6edf3",
                    borderRadius: 4,
                  }}
                >
                  <div style={{ fontWeight: 700 }}>{d.name}</div>
                  <div style={{ color: d.pnl_pct >= 0 ? "#3fb950" : "#f85149" }}>
                    {d.pnl_pct >= 0 ? "+" : ""}
                    {d.pnl_pct.toFixed(2)}%
                  </div>
                </div>
              );
            }}
          />
        </Treemap>
      </ResponsiveContainer>
    </div>
  );
}
