import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

const SUIT_CLASS = {
  "♥": "text-suit-heart",
  "♦": "text-suit-diamond",
  "♣": "text-suit-club",
  "♠": "text-suit-spade",
};

function colorSuits(children) {
  if (typeof children !== "string") return children;
  const parts = children.split(/(♥|♦|♣|♠)/);
  if (parts.length === 1) return children;
  return parts.map((part, i) =>
    SUIT_CLASS[part] ? (
      <span key={i} className={cn("font-bold", SUIT_CLASS[part])}>
        {part}
      </span>
    ) : (
      part
    )
  );
}

function applyToChildren(children) {
  if (Array.isArray(children))
    return children.map((c, i) => (typeof c === "string" ? <span key={i}>{colorSuits(c)}</span> : c));
  return colorSuits(children);
}

const MARKDOWN_COMPONENTS = {
  p: ({ children }) => <p className="mb-3">{applyToChildren(children)}</p>,
  ul: ({ children }) => <ul className="mb-3 list-disc space-y-1.5 pl-5 marker:text-ink-subtle">{children}</ul>,
  ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1.5 pl-5 marker:text-ink-subtle">{children}</ol>,
  li: ({ children }) => <li>{applyToChildren(children)}</li>,
  strong: ({ children }) => <strong className="font-semibold text-gold">{applyToChildren(children)}</strong>,
  em: ({ children }) => <em className="not-italic text-sky">{applyToChildren(children)}</em>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-sky underline underline-offset-4">
      {children}
    </a>
  ),
  code: ({ inline, children }) =>
    inline ? (
      <code className="rounded-md border border-line bg-black/25 px-1.5 py-0.5 text-[12px] text-gold">{children}</code>
    ) : (
      <pre className="mb-3 overflow-x-auto rounded-control border border-line bg-black/30 px-4 py-3 text-[12px] leading-6 text-ink">
        <code>{children}</code>
      </pre>
    ),
  h1: ({ children }) => <h1 className="pixel-font mb-3 mt-5 text-[20px] text-gold">{children}</h1>,
  h2: ({ children }) => <h2 className="pixel-font mb-3 mt-5 text-[18px] text-suit-club">{children}</h2>,
  h3: ({ children }) => <h3 className="pixel-font mb-2 mt-4 text-[16px] text-sky">{children}</h3>,
  blockquote: ({ children }) => (
    <blockquote className="mb-3 rounded-control bg-black/20 px-4 py-2 text-ink-muted">{children}</blockquote>
  ),
  table: ({ children }) => (
    <div className="mb-3 overflow-x-auto">
      <table className="w-full border-collapse text-[12px]">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="border-b-2 border-line-strong">{children}</thead>,
  tbody: ({ children }) => <tbody>{children}</tbody>,
  tr: ({ children }) => <tr className="border-b border-line last:border-0">{children}</tr>,
  th: ({ children }) => <th className="px-3 py-2 text-left font-semibold text-gold">{children}</th>,
  td: ({ children }) => <td className="px-3 py-2 text-ink-muted">{applyToChildren(children)}</td>,
};

const ROLE_META = {
  user: { name: "You", bubble: "chat-bubble-user" },
  system: { name: "Table Alert", bubble: "chat-bubble-system", label: "text-[#ffd6d6]" },
  assistant: { name: "Joker Coach", bubble: "chat-bubble-assistant", label: "text-sky" },
};

export default function ChatMessage({ role, content, streaming, imagePreviews = [] }) {
  const isUser = role === "user";
  const isSystem = role === "system";
  const meta = ROLE_META[role] ?? ROLE_META.assistant;
  const showLoader = streaming && !content.trim();

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("min-w-0 max-w-[92%] sm:max-w-[80%]", isUser && "flex flex-col items-end")}>
        {!isUser ? (
          <p className={cn("pixel-font mb-2 flex items-center gap-2 text-[13px]", meta.label)}>
            {isSystem ? <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" /> : null}
            {meta.name}
            {streaming && !showLoader ? <span className="text-ink-subtle">· Thinking</span> : null}
          </p>
        ) : (
          <p className="sr-only">You said:</p>
        )}

        <div className={cn("chat-bubble", meta.bubble)}>
          {imagePreviews.length > 0 ? (
            <div className={cn("mb-3 grid gap-2", imagePreviews.length === 1 ? "grid-cols-1" : "grid-cols-2")}>
              {imagePreviews.map((preview, index) => (
                <img
                  key={`${preview}-${index}`}
                  src={preview}
                  alt={`Uploaded screenshot ${index + 1}`}
                  className={cn(
                    "max-h-[220px] w-full object-cover",
                    imagePreviews.length === 3 && index === 0 && "col-span-2"
                  )}
                />
              ))}
            </div>
          ) : null}

          {showLoader ? (
            <div className="flex items-center gap-3 py-1" role="status">
              <span className="thinking-dots" aria-hidden="true">
                <span className="thinking-dot" />
                <span className="thinking-dot" />
                <span className="thinking-dot" />
              </span>
              <span className="pixel-font text-[13px] text-gold">Reading the table</span>
            </div>
          ) : isUser ? (
            <p className="terminal-copy whitespace-pre-wrap text-[13px] leading-6 text-inherit">{content}</p>
          ) : (
            <div className="markdown-copy terminal-copy text-[13px] leading-6 text-inherit">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
                {content}
              </ReactMarkdown>
              {streaming ? <span className="streaming-cursor" aria-hidden="true" /> : null}
            </div>
          )}

          {isSystem ? (
            <p className="terminal-copy mt-3 border-t border-white/10 pt-3 text-[12px] text-[#ffd6d6]">
              Something interrupted the request. Retrying is safe.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
