import { useEffect, useRef, useState } from "react";
import { useChat } from "./hooks/useChat";
import ChatMessage from "./components/ChatMessage";
import GameStateCard from "./components/GameStateCard";
import ImageUploader from "./components/ImageUploader";

const SUGGESTED_PROMPTS = [
  "What should I play next?",
  "What's the best buy in the shop?",
  "Should I skip this blind?",
  "How do my jokers synergise?",
  "What hand type should I build toward?",
];

export default function App() {
  const { messages, gameState, isLoading, sendMessage, clearChat } = useChat();
  const [input, setInput] = useState("");
  const [imageFile, setImageFile] = useState(null);
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text && !imageFile) return;
    sendMessage(text || "(screenshot uploaded – please analyse my game state)", imageFile);
    setInput("");
    setImageFile(null);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const isEmpty = messages.length === 0;

  return (
    <div style={styles.root}>
      {/* ── Sidebar ──────────────────────────────────────────────── */}
      <aside style={styles.sidebar}>
        <div style={styles.logoRow}>
          <span style={styles.logo}>🃏</span>
          <span style={styles.logoText}>Balatro Coach</span>
        </div>

        <p style={styles.sidebarDesc}>
          Upload a screenshot of your game and ask for coaching advice. The AI reads your jokers,
          hand, score, and shop automatically.
        </p>

        <div style={styles.divider} />

        {/* Game state card */}
        {gameState ? (
          <>
            <div style={styles.sidebarLabel}>Game State</div>
            <GameStateCard state={gameState} />
          </>
        ) : (
          <div style={styles.noState}>No game state extracted yet. Upload a screenshot to start.</div>
        )}

        <div style={styles.divider} />

        <div style={styles.sidebarLabel}>Quick prompts</div>
        <div style={styles.quickPrompts}>
          {SUGGESTED_PROMPTS.map((p) => (
            <button
              key={p}
              style={styles.quickBtn}
              onClick={() => {
                setInput(p);
                textareaRef.current?.focus();
              }}
            >
              {p}
            </button>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        {messages.length > 0 && (
          <button style={styles.clearBtn} onClick={clearChat}>
            Clear conversation
          </button>
        )}
      </aside>

      {/* ── Main chat ────────────────────────────────────────────── */}
      <main style={styles.main}>
        <div style={styles.messageList}>
          {isEmpty ? (
            <div style={styles.emptyState}>
              <div style={styles.emptyIcon}>🎯</div>
              <h2 style={styles.emptyTitle}>Balatro Coach</h2>
              <p style={styles.emptyDesc}>
                Upload a screenshot or describe your game state to get expert coaching.
                Ask about plays, shop decisions, blind skips, or joker synergies.
              </p>
            </div>
          ) : (
            messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                role={msg.role}
                content={msg.content}
                streaming={msg.streaming}
                imagePreview={msg.imagePreview}
              />
            ))
          )}
          <div ref={bottomRef} />
        </div>

        {/* ── Input area ───────────────────────────────────────────── */}
        <div style={styles.inputArea}>
          <ImageUploader onFile={setImageFile} disabled={isLoading} />

          <div style={styles.inputRow}>
            <textarea
              ref={textareaRef}
              style={styles.textarea}
              placeholder="Ask for coaching… or just upload a screenshot"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
              disabled={isLoading}
            />
            <button
              style={{
                ...styles.sendBtn,
                ...(isLoading || (!input.trim() && !imageFile) ? styles.sendBtnDisabled : {}),
              }}
              onClick={handleSend}
              disabled={isLoading || (!input.trim() && !imageFile)}
            >
              {isLoading ? <Spinner /> : "Send"}
            </button>
          </div>
          <p style={styles.hint}>Enter to send · Shift+Enter for new line · Ctrl+V to paste screenshot</p>
        </div>
      </main>

      <style>{`
        @keyframes blink { 0%,100% { opacity: 1 } 50% { opacity: 0 } }
        @keyframes spin { to { transform: rotate(360deg) } }
        * { box-sizing: border-box; }
        body { margin: 0; background: #0f0f14; font-family: system-ui, sans-serif; }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 3px; }
      `}</style>
    </div>
  );
}

function Spinner() {
  return (
    <span
      style={{
        display: "inline-block",
        width: 14,
        height: 14,
        border: "2px solid rgba(255,255,255,0.2)",
        borderTopColor: "#fff",
        borderRadius: "50%",
        animation: "spin 0.7s linear infinite",
      }}
    />
  );
}

const styles = {
  root: {
    display: "flex",
    height: "100vh",
    color: "#e2e8f0",
    overflow: "hidden",
  },
  // ── Sidebar ───────────────────────────────────────────────────────────────
  sidebar: {
    width: 300,
    flexShrink: 0,
    background: "#13131a",
    borderRight: "1px solid rgba(255,255,255,0.07)",
    display: "flex",
    flexDirection: "column",
    padding: "20px 16px",
    overflowY: "auto",
    gap: 10,
  },
  logoRow: { display: "flex", alignItems: "center", gap: 10, marginBottom: 4 },
  logo: { fontSize: 26 },
  logoText: { fontSize: 18, fontWeight: 700, color: "#e0e7ff", letterSpacing: "-0.01em" },
  sidebarDesc: { fontSize: 12, color: "#475569", lineHeight: 1.6, margin: 0 },
  divider: { height: 1, background: "rgba(255,255,255,0.07)", margin: "4px 0" },
  sidebarLabel: {
    fontSize: 11,
    color: "#475569",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    fontWeight: 500,
  },
  noState: {
    fontSize: 12,
    color: "#334155",
    fontStyle: "italic",
    lineHeight: 1.5,
  },
  quickPrompts: { display: "flex", flexDirection: "column", gap: 5 },
  quickBtn: {
    background: "rgba(99,102,241,0.08)",
    border: "1px solid rgba(99,102,241,0.2)",
    color: "#a5b4fc",
    borderRadius: 7,
    padding: "7px 10px",
    fontSize: 12,
    cursor: "pointer",
    textAlign: "left",
    transition: "background 0.15s",
  },
  clearBtn: {
    background: "transparent",
    border: "1px solid rgba(255,255,255,0.1)",
    color: "#64748b",
    borderRadius: 7,
    padding: "7px 10px",
    fontSize: 12,
    cursor: "pointer",
    marginTop: 8,
  },
  // ── Main ─────────────────────────────────────────────────────────────────
  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    background: "#0f0f14",
  },
  messageList: {
    flex: 1,
    overflowY: "auto",
    padding: "24px 28px 12px",
    display: "flex",
    flexDirection: "column",
  },
  emptyState: {
    margin: "auto",
    textAlign: "center",
    maxWidth: 420,
    padding: "60px 20px",
  },
  emptyIcon: { fontSize: 48, marginBottom: 16 },
  emptyTitle: { fontSize: 22, fontWeight: 700, color: "#e0e7ff", margin: "0 0 10px" },
  emptyDesc: { fontSize: 14, color: "#475569", lineHeight: 1.7, margin: 0 },
  // ── Input ─────────────────────────────────────────────────────────────────
  inputArea: {
    padding: "12px 28px 16px",
    borderTop: "1px solid rgba(255,255,255,0.07)",
    display: "flex",
    flexDirection: "column",
    gap: 8,
    background: "#0f0f14",
  },
  inputRow: { display: "flex", gap: 8, alignItems: "flex-end" },
  textarea: {
    flex: 1,
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 10,
    color: "#e2e8f0",
    padding: "10px 14px",
    fontSize: 14,
    resize: "none",
    outline: "none",
    lineHeight: 1.5,
    fontFamily: "inherit",
  },
  sendBtn: {
    background: "#4f46e5",
    color: "#fff",
    border: "none",
    borderRadius: 10,
    padding: "10px 20px",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    height: 44,
    minWidth: 72,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    transition: "background 0.15s",
  },
  sendBtnDisabled: { background: "#2d2d3d", cursor: "not-allowed" },
  hint: { fontSize: 11, color: "#334155", margin: 0 },
};
