import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// Must mock before importing component
jest.mock("@/lib/AppContext", () => ({
  useApp: () => ({
    prices: new Map([
      ["AAPL", { price: 192.5, prev_price: 191.0, direction: "up" }],
      ["GOOGL", { price: 175.0, prev_price: 175.0, direction: "unchanged" }],
    ]),
    priceHistory: new Map([["AAPL", [190, 191, 192.5]]]),
    watchlist: ["AAPL", "GOOGL", "MSFT"],
    selectedTicker: "AAPL",
    setSelectedTicker: jest.fn(),
    refreshWatchlist: jest.fn().mockResolvedValue(undefined),
  }),
}));

jest.mock("@/lib/api", () => ({
  addToWatchlist: jest.fn().mockResolvedValue({ ticker: "TSLA" }),
  removeFromWatchlist: jest.fn().mockResolvedValue(undefined),
}));

import Watchlist from "@/components/Watchlist";

describe("Watchlist", () => {
  it("renders ticker rows from watchlist", () => {
    render(<Watchlist />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("GOOGL")).toBeInTheDocument();
    expect(screen.getByText("MSFT")).toBeInTheDocument();
  });

  it("renders price for tickers with data", () => {
    render(<Watchlist />);
    expect(screen.getByText("$192.50")).toBeInTheDocument();
    expect(screen.getByText("$175.00")).toBeInTheDocument();
  });

  it("shows add ticker input", () => {
    render(<Watchlist />);
    expect(
      screen.getByPlaceholderText("Add ticker...")
    ).toBeInTheDocument();
    expect(screen.getByText("Add")).toBeInTheDocument();
  });
});
