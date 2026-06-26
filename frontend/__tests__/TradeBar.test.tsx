import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

const mockExecuteTrade = jest.fn();
const mockRefreshPortfolio = jest.fn().mockResolvedValue(undefined);
const mockRefreshHistory = jest.fn().mockResolvedValue(undefined);

jest.mock("@/lib/AppContext", () => ({
  useApp: () => ({
    selectedTicker: "AAPL",
    refreshPortfolio: mockRefreshPortfolio,
    refreshHistory: mockRefreshHistory,
  }),
}));

jest.mock("@/lib/api", () => ({
  executeTrade: (...args: unknown[]) => mockExecuteTrade(...args),
}));

import TradeBar from "@/components/TradeBar";

describe("TradeBar", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders buy and sell buttons", () => {
    render(<TradeBar />);
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("SELL")).toBeInTheDocument();
  });

  it("renders quantity input", () => {
    render(<TradeBar />);
    expect(screen.getByPlaceholderText("Qty")).toBeInTheDocument();
  });

  it("calls executeTrade with correct args on buy", async () => {
    mockExecuteTrade.mockResolvedValue({
      ok: true,
      ticker: "AAPL",
      side: "buy",
      quantity: 5,
      price: 192.5,
      cash_remaining: 7537.5,
    });

    render(<TradeBar />);

    const qtyInput = screen.getByPlaceholderText("Qty");
    fireEvent.change(qtyInput, { target: { value: "5" } });
    fireEvent.click(screen.getByText("BUY"));

    await waitFor(() => {
      expect(mockExecuteTrade).toHaveBeenCalledWith("AAPL", 5, "buy");
    });
  });

  it("shows error when no quantity given", async () => {
    render(<TradeBar />);
    fireEvent.click(screen.getByText("BUY"));

    await waitFor(() => {
      expect(
        screen.getByText("Enter a valid ticker and quantity")
      ).toBeInTheDocument();
    });
  });
});
