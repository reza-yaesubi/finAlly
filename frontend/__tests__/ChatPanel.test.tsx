import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

const mockSendChat = jest.fn();

jest.mock("@/lib/AppContext", () => ({
  useApp: () => ({
    refreshPortfolio: jest.fn().mockResolvedValue(undefined),
    refreshWatchlist: jest.fn().mockResolvedValue(undefined),
    refreshHistory: jest.fn().mockResolvedValue(undefined),
  }),
}));

jest.mock("@/lib/api", () => ({
  sendChatMessage: (...args: unknown[]) => mockSendChat(...args),
}));

import ChatPanel from "@/components/ChatPanel";

describe("ChatPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders message input and send button", () => {
    render(<ChatPanel />);
    expect(screen.getByPlaceholderText("Ask FinAlly...")).toBeInTheDocument();
    expect(screen.getByText("Send")).toBeInTheDocument();
  });

  it("shows placeholder text when no messages", () => {
    render(<ChatPanel />);
    expect(
      screen.getByText(/Ask me about your portfolio/)
    ).toBeInTheDocument();
  });

  it("sends message and shows response", async () => {
    mockSendChat.mockResolvedValue({
      message: "Your portfolio is healthy!",
      trades: [],
      watchlist_changes: [],
    });

    render(<ChatPanel />);

    const input = screen.getByPlaceholderText("Ask FinAlly...");
    fireEvent.change(input, { target: { value: "How is my portfolio?" } });
    fireEvent.click(screen.getByText("Send"));

    expect(screen.getByText("How is my portfolio?")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Your portfolio is healthy!")).toBeInTheDocument();
    });
  });

  it("shows trade action confirmation", async () => {
    mockSendChat.mockResolvedValue({
      message: "Done, I bought 5 AAPL.",
      trades: [
        { ticker: "AAPL", side: "buy", quantity: 5, price: 192.5, status: "executed" },
      ],
      watchlist_changes: [],
    });

    render(<ChatPanel />);

    const input = screen.getByPlaceholderText("Ask FinAlly...");
    fireEvent.change(input, { target: { value: "Buy 5 AAPL" } });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() => {
      expect(screen.getByText(/Bought 5 AAPL @ \$192\.50/)).toBeInTheDocument();
    });
  });
});
