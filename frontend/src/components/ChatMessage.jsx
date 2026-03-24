import ReactMarkdown from "react-markdown";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";

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
    <div className={cn("mb-4 flex items-start gap-3", isUser && "flex-row-reverse")}>
      <Avatar size="sm">
        <AvatarFallback>
          {isUser ? "🃏" : isSystem ? "⚠️" : "🎯"}
        </AvatarFallback>
      </Avatar>
      <div
        className={cn(
          "max-w-[85%] rounded-xl border px-4 py-3 text-sm leading-6 shadow-sm",
          isUser &&
            "rounded-tr-sm border-primary/50 bg-primary/15 text-foreground",
          !isUser &&
            !isSystem &&
            "rounded-tl-sm border-border bg-card text-card-foreground",
          isSystem && "border-secondary/50 bg-secondary/10 text-foreground"
        )}
      >
        {/* Image preview inside user message */}
        {imagePreview && (
          <img
            src={imagePreview}
            alt="screenshot"
            className="mb-3 max-h-56 w-full rounded-md object-contain"
          />
        )}

        {/* Text content */}
        {isUser ? (
          <span className="whitespace-pre-wrap">{content}</span>
        ) : (
          <div className="inline">
            <ReactMarkdown
              components={{
                p: ({ children }) => <p className="mb-2">{children}</p>,
                ul: ({ children }) => <ul className="mb-2 list-disc pl-5">{children}</ul>,
                ol: ({ children }) => <ol className="mb-2 list-decimal pl-5">{children}</ol>,
                li: ({ children }) => <li className="mb-1">{children}</li>,
                strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                code: ({ inline, children }) =>
                  inline ? (
                    <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-accent">{children}</code>
                  ) : (
                    <pre className="my-2 overflow-x-auto rounded-md border border-border bg-muted/50 px-3 py-2 font-mono text-xs text-accent">
                      <code>{children}</code>
                    </pre>
                  ),
                h3: ({ children }) => <h3 className="mb-1 mt-3 font-heading text-sm text-accent">{children}</h3>,
              }}
            >
              {content}
            </ReactMarkdown>
            {streaming && <span className="ml-1 inline-block animate-pulse text-accent">▍</span>}
          </div>
        )}
      </div>
    </div>
  );
}
