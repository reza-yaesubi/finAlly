"use client";

import { useState, useRef, useEffect } from "react";
import { useApp } from "@/lib/AppContext";
import { sendChatMessage } from "@/lib/api";
import type { ChatMessage, ChatTradeAction, ChatWatchlistChange } from "@/lib/types";

let msgId = 0;
function nextId() {
  return String(++msgId);
}

function TradeActions({
  trades,
  watchlist_changes,
}: {
  trades?: ChatTradeAction[];
  watchlist_changes?: ChatWatchlistChange[];
}) {
  const hasTrades = trades && trades.length > 0;
  const hasChanges = watchlist_changes && watchlist_changes.length > 0;
  if (!hasTrades && !hasChanges) return null;

  return (
    <div style={{ marginTop: 6 }}>
      {trades?.map((t, i) => (
        <div
          key={i}
          style={{
            fontSize: 11,
            color: t.status === "executed" ? "#3fb950" : "#f85149",
            padding: "2px 0",
          }}
        >
          {t.status === "executed"
            ? `${t.side === "buy" ? "Bought" : "Sold"} ${t.quantity} ${t.ticker}${t.price ? ` @ $${t.price.toFixed(2)}` : ""}`
            : `Failed: ${t.ticker} ${t.side} — ${t.error ?? "unknown error"}`}
        </div>
      ))}
      {watchlist_changes?.map((c, i) => (
        <div
          key={i}
          style={{
            fontSize: 11,
            color: c.status === "executed" ? "#209dd7" : "#f85149",
            padding: "2px 0",
          }}
        >
          {c.status === "executed"
            ? `Added ${c.ticker} to watchlist`
            : `Failed to add ${c.ticker}`}
        </div>
      ))}
    </div>
  );
}

export default function ChatPanel() {
  const { refreshPortfolio, refreshWatchlist, refreshHistory } = useApp();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = {
      id: nextId(),
      role: "user",
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const resp = await sendChatMessage(text);
      const assistantMsg: ChatMessage = {
        id: nextId(),
        role: "assistant",
        content: resp.message,
        trades: resp.trades,
        watchlist_changes: resp.watchlist_changes,
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // Refresh state if AI executed actions
      if (resp.trades?.length > 0 || resp.watchlist_changes?.length > 0) {
        await Promise.all([
          refreshPortfolio(),
          refreshWatchlist(),
          refreshHistory(),
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "assistant",
          content: "Sorry, I encountered an error. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "#161b22",
        borderLeft: "1px solid #30363d",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "8px 12px 6px",
          borderBottom: "1px solid #30363d",
          flexShrink: 0,
        }}
      >
        <span style={{ color: "#8b949e", fontSize: 10, letterSpacing: 1 }}>
          AI ASSISTANT
        </span>
        <span style={{ color: "#753991", fontSize: 10, marginLeft: 6 }}>
          FINALLY
        </span>
      </div>

      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "10px 10px",
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        {messages.length === 0 && (
          <div style={{ color: "#8b949e", fontSize: 12, textAlign: "center", marginTop: 24 }}>
            Ask me about your portfolio, get analysis, or say "Buy 5 AAPL"
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: msg.role === "user" ? "flex-end" : "flex-start",
            }}
          >
            <div
              style={{
                maxWidth: "85%",
                background: msg.role === "user" ? "#209dd7" : "#21262d",
                color: "#e6edf3",
                padding: "7px 10px",
                borderRadius:
                  msg.role === "user"
                    ? "12px 12px 2px 12px"
                    : "12px 12px 12px 2px",
                fontSize: 13,
                lineHeight: 1.5,
              }}
            >
              {msg.content}
              {msg.role === "assistant" && (
                <TradeActions
                  trades={msg.trades}
                  watchlist_changes={msg.watchlist_changes}
                />
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: "flex", alignItems: "flex-start" }}>
            <div
              style={{
                background: "#21262d",
                color: "#8b949e",
                padding: "7px 12px",
                borderRadius: "12px 12px 12px 2px",
                fontSize: 13,
              }}
            >
              <span style={{ letterSpacing: 2 }}>...</span>
            </div>
          </div>
        )}
      </div>

      <div
        style={{
          padding: "8px 10px",
          borderTop: "1px solid #30363d",
          flexShrink: 0,
          display: "flex",
          gap: 6,
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="Ask FinAlly..."
          disabled={loading}
          style={{
            flex: 1,
            background: "#0d1117",
            border: "1px solid #30363d",
            color: "#e6edf3",
            padding: "7px 10px",
            fontSize: 13,
            borderRadius: 4,
            outline: "none",
          }}
        />
        <button
          onClick={handleSend}
          disabled={loading}
          style={{
            background: loading ? "#4a2360" : "#753991",
            border: "none",
            color: "#fff",
            padding: "7px 14px",
            fontSize: 12,
            borderRadius: 4,
            cursor: loading ? "not-allowed" : "pointer",
            fontWeight: 700,
            transition: "background 0.15s",
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
