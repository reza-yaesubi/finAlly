import React from "react";

export const mockAppState = {
  prices: new Map([
    ["AAPL", { price: 192.5, prev_price: 191.0, direction: "up" as const }],
    ["GOOGL", { price: 175.0, prev_price: 175.0, direction: "unchanged" as const }],
  ]),
  priceHistory: new Map([
    ["AAPL", [190, 191, 192, 191.5, 192.5]],
  ]),
  watchlist: ["AAPL", "GOOGL", "MSFT"],
  portfolio: {
    cash: 7500,
    total_value: 10250,
    positions: [
      {
        ticker: "AAPL",
        quantity: 10,
        avg_cost: 190.0,
        current_price: 192.5,
        unrealized_pnl: 25.0,
        pnl_pct: 1.32,
      },
    ],
  },
  portfolioHistory: [
    { recorded_at: "2024-01-01T10:00:00Z", total_value: 10000 },
    { recorded_at: "2024-01-01T10:01:00Z", total_value: 10250 },
  ],
  selectedTicker: "AAPL",
  connectionStatus: "connected" as const,
  setSelectedTicker: jest.fn(),
  setWatchlist: jest.fn(),
  refreshPortfolio: jest.fn().mockResolvedValue(undefined),
  refreshWatchlist: jest.fn().mockResolvedValue(undefined),
  refreshHistory: jest.fn().mockResolvedValue(undefined),
};

jest.mock("@/lib/AppContext", () => ({
  useApp: () => mockAppState,
  AppProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
