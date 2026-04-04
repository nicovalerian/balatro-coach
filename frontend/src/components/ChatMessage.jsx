import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

const SUIT_COLORS = {
  "♥": "#e43f3f",
  "♦": "#ff8f00",
  "♣": "#4ade80",
  "♠": "#8ac9ff",
};

function colorSuits(children) {
  if (typeof children !== "string") return children;
  const parts = children.split(/(♥|♦|♣|♠)/);
  if (parts.length === 1) return children;
  return parts.map((part, i) =>
    SUIT_COLORS[part]
      ? <span key={i} style={{ color: SUIT_COLORS[part], fontWeight: 700 }}>{part}</span>
      : part
  );
}

function applyToChildren(children) {
  if (Array.isArray(children)) return children.map((c, i) =>
    typeof c === "string" ? <span key={i}>{colorSuits(c)}</span> : c
  );
  return colorSuits(children);
}

export default function ChatMessage({
  role,
  content,
  streaming,
  imagePreviews = [],
}) {
  const isUser = role === "user";
  const isSystem = role === "system";

  const meta = isUser
    ? {
        name: "You",
        label: "Player",
        bubbleClass: "chat-bubble-user",
        labelClass: "text-[#1b170a]",
      }
    : isSystem
      ? {
          name: "Table Alert",
          label: "Warning",
          bubbleClass: "chat-bubble-system",
          labelClass: "text-[#ffdede]",
        }
      : {
          name: "Joker Coach",
          label: streaming ? "Thinking" : "Coach",
          bubbleClass: "chat-bubble-assistant",
          labelClass: "text-[#d8ebff]",
        };

  const showLoader = streaming && !content.trim();

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-[92%] sm:max-w-[84%]", isUser && "items-end")}>
        {!isUser ? (
          <div className="mb-2 flex items-center gap-2">
            <span className={cn("pixel-font text-[12px]", meta.labelClass)}>{meta.name}</span>
            <span className="inline-flex min-h-[24px] items-center justify-center rounded-full border border-white/10 bg-black/20 px-2 py-1">
              <span className={cn("pixel-font text-[10px]", meta.labelClass)}>{meta.label}</span>
            </span>
          </div>
        ) : null}

        <div className={cn("chat-bubble", meta.bubbleClass)}>
          {imagePreviews.length > 0 ? (
            <div
              className={cn(
                "mb-4 grid gap-3",
                imagePreviews.length === 1 ? "grid-cols-1" : "grid-cols-2"
              )}
            >
              {imagePreviews.map((preview, index) => (
                <img
                  key={`${preview}-${index}`}
                  src={preview}
                  alt={`uploaded screenshot ${index + 1}`}
                  className={cn(
                    "w-full object-contain",
                    imagePreviews.length === 3 && index === 0 && "col-span-2"
                  )}
                />
              ))}
            </div>
          ) : null}

          {showLoader ? (
            <div className="flex items-center gap-3">
              <span className="card-loader" aria-hidden="true" />
              <div>
                <p className="pixel-font text-[13px] text-[#f2c237]">Reading The Table</p>
                <p className="terminal-copy mt-1 text-[12px] text-[#d0d8d3]">
                  Checking blind pressure, score lines, and joker order.
                </p>
              </div>
            </div>
          ) : isUser ? (
            <p className="terminal-copy whitespace-pre-wrap text-[13px] leading-6 text-inherit">
              {content}
            </p>
          ) : (
            <div className="markdown-copy terminal-copy text-[13px] leading-6 text-inherit">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ children }) => <p className="mb-3">{applyToChildren(children)}</p>,
                  ul: ({ children }) => <ul className="mb-3 list-disc space-y-1 pl-5">{children}</ul>,
                  ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1 pl-5">{children}</ol>,
                  li: ({ children }) => <li>{applyToChildren(children)}</li>,
                  strong: ({ children }) => (
                    <strong className="font-semibold text-[#f2c237]">{applyToChildren(children)}</strong>
                  ),
                  em: ({ children }) => (
                    <em className="not-italic text-[#8ac9ff]">{applyToChildren(children)}</em>
                  ),
                  a: ({ children, href }) => (
                    <a
                      href={href}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[#8ac9ff] underline underline-offset-4"
                    >
                      {children}
                    </a>
                  ),
                  code: ({ inline, children }) =>
                    inline ? (
                      <code className="rounded-[8px] border border-white/10 bg-black/25 px-2 py-1 text-[12px] text-[#f2c237]">
                        {children}
                      </code>
                    ) : (
                      <pre className="mb-3 overflow-x-auto rounded-[14px] border border-white/10 bg-black/30 px-4 py-3 text-[12px] leading-6 text-[#e3ece7]">
                        <code>{children}</code>
                      </pre>
                    ),
                  h1: ({ children }) => (
                    <h1 className="pixel-font mb-3 text-[18px] text-[#f2c237]">{children}</h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="pixel-font mb-3 text-[16px] text-[#4ade80]">{children}</h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="pixel-font mb-2 text-[14px] text-[#8ac9ff]">{children}</h3>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote className="mb-3 border-l-2 border-[#3498db] pl-4 text-[#dceeff]">
                      {children}
                    </blockquote>
                  ),
                  table: ({ children }) => (
                    <div className="mb-3 overflow-x-auto">
                      <table className="w-full border-collapse text-[12px]">{children}</table>
                    </div>
                  ),
                  thead: ({ children }) => (
                    <thead className="border-b border-white/20">{children}</thead>
                  ),
                  tbody: ({ children }) => <tbody>{children}</tbody>,
                  tr: ({ children }) => (
                    <tr className="border-b border-white/8 last:border-0">{children}</tr>
                  ),
                  th: ({ children }) => (
                    <th className="px-3 py-1.5 text-left font-semibold text-[#f2c237]">{children}</th>
                  ),
                  td: ({ children }) => (
                    <td className="px-3 py-1.5 text-[#dce3de]">{applyToChildren(children)}</td>
                  ),
                }}
              >
                {content}
              </ReactMarkdown>

              {streaming ? (
                <div className="mt-3 flex items-center gap-2 text-[#f2c237]">
                  <span className="card-loader scale-75" aria-hidden="true" />
                  <span className="pixel-font text-[11px]">Building Response</span>
                </div>
              ) : null}
            </div>
          )}

          {isSystem ? (
            <div className="mt-3 flex items-center gap-2 text-[#ffdede]">
              <AlertTriangle className="h-4 w-4" />
              <span className="terminal-copy text-[12px]">
                Something interrupted the request. Retrying is safe.
              </span>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
