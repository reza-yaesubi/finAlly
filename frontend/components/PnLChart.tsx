"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { useApp } from "@/lib/AppContext";

function fmtTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
}

function fmtDollar(v: number) {
  return v.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0 });
}

export default function PnLChart() {
  const { portfolioHistory } = useApp();

  if (portfolioHistory.length === 0) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span style={{ color: "#8b949e", fontSize: 12 }}>
          Waiting for portfolio data...
        </span>
      </div>
    );
  }

  const data = portfolioHistory.map((p) => ({
    time: fmtTime(p.recorded_at),
    value: p.total_value,
  }));

  const baseline = data[0]?.value ?? 10000;
  const latest = data[data.length - 1]?.value ?? baseline;
  const lineColor = latest >= baseline ? "#3fb950" : "#f85149";

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
        <XAxis
          dataKey="time"
          tick={{ fill: "#8b949e", fontSize: 9 }}
          tickLine={false}
          axisLine={{ stroke: "#30363d" }}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fill: "#8b949e", fontSize: 9 }}
          tickLine={false}
          axisLine={{ stroke: "#30363d" }}
          tickFormatter={fmtDollar}
          width={72}
        />
        <Tooltip
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null;
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
                <div style={{ color: "#8b949e", fontSize: 10 }}>{label}</div>
                <div style={{ fontWeight: 700 }}>
                  {fmtDollar(payload[0].value as number)}
                </div>
              </div>
            );
          }}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke={lineColor}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 3, fill: lineColor }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
