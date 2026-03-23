import ReactMarkdown from "react-markdown";

/**
 * ChatMessage
 * Renders a single message bubble.
 * role: "user" | "assistant" | "system"
 * streaming: bool – shows a blinking cursor while content arrives
 */
export default function ChatMessage({ role, content, streaming, imagePreview }) {
  const isUser = role === "user";
  const isSystem = role === "system";

  return (
    <div style={{ ...styles.wrap, ...(isUser ? styles.wrapUser : {}) }}>
      <div style={styles.avatar}>{isUser ? "🃏" : isSystem ? "⚠️" : "🎯"}</div>
      <div
        style={{
          ...styles.bubble,
          ...(isUser ? styles.bubbleUser : isSystem ? styles.bubbleSystem : styles.bubbleAssistant),
        }}
      >
        {/* Image preview inside user message */}
        {imagePreview && (
          <img
            src={imagePreview}
            alt="screenshot"
            style={styles.inlineImg}
          />
        )}

        {/* Text content */}
        {isUser ? (
          <span style={styles.userText}>{content}</span>
        ) : (
          <div style={styles.markdownWrap}>
            <ReactMarkdown
              components={{
                p: ({ children }) => <p style={styles.p}>{children}</p>,
                ul: ({ children }) => <ul style={styles.ul}>{children}</ul>,
                ol: ({ children }) => <ol style={styles.ol}>{children}</ol>,
                li: ({ children }) => <li style={styles.li}>{children}</li>,
                strong: ({ children }) => <strong style={styles.strong}>{children}</strong>,
                code: ({ inline, children }) =>
                  inline ? (
                    <code style={styles.inlineCode}>{children}</code>
                  ) : (
                    <pre style={styles.codeBlock}><code>{children}</code></pre>
                  ),
                h3: ({ children }) => <h3 style={styles.h3}>{children}</h3>,
              }}
            >
              {content}
            </ReactMarkdown>
            {streaming && <span style={styles.cursor}>▍</span>}
          </div>
        )}
      </div>
    </div>
  );
}

const styles = {
  wrap: {
    display: "flex",
    gap: 10,
    alignItems: "flex-start",
    marginBottom: 16,
  },
  wrapUser: { flexDirection: "row-reverse" },
  avatar: {
    fontSize: 18,
    width: 32,
    height: 32,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    marginTop: 2,
  },
  bubble: {
    maxWidth: "82%",
    borderRadius: 12,
    padding: "10px 14px",
    fontSize: 14,
    lineHeight: 1.6,
  },
  bubbleUser: {
    background: "rgba(99,102,241,0.2)",
    border: "1px solid rgba(99,102,241,0.35)",
    color: "#e0e7ff",
    borderTopRightRadius: 4,
  },
  bubbleAssistant: {
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.09)",
    color: "#e2e8f0",
    borderTopLeftRadius: 4,
  },
  bubbleSystem: {
    background: "rgba(251,191,36,0.08)",
    border: "1px solid rgba(251,191,36,0.25)",
    color: "#fde68a",
    borderRadius: 10,
    fontSize: 13,
  },
  userText: { whiteSpace: "pre-wrap" },
  markdownWrap: { display: "inline" },
  inlineImg: {
    width: "100%",
    borderRadius: 8,
    display: "block",
    marginBottom: 8,
    maxHeight: 200,
    objectFit: "contain",
  },
  p: { margin: "0 0 8px 0" },
  ul: { margin: "4px 0 8px 0", paddingLeft: 20 },
  ol: { margin: "4px 0 8px 0", paddingLeft: 20 },
  li: { marginBottom: 3 },
  strong: { color: "#f0f9ff", fontWeight: 600 },
  h3: { margin: "10px 0 4px", fontSize: 14, color: "#c7d2fe", fontWeight: 600 },
  inlineCode: {
    background: "rgba(0,0,0,0.3)",
    borderRadius: 4,
    padding: "1px 5px",
    fontSize: 13,
    fontFamily: "monospace",
    color: "#a5f3fc",
  },
  codeBlock: {
    background: "rgba(0,0,0,0.4)",
    borderRadius: 7,
    padding: "8px 12px",
    fontSize: 12,
    fontFamily: "monospace",
    overflowX: "auto",
    margin: "6px 0",
    color: "#a5f3fc",
  },
  cursor: {
    display: "inline-block",
    animation: "blink 1s step-end infinite",
    color: "#818cf8",
    marginLeft: 1,
  },
};
