// Adapted from prompt-kit "ChatContainer" + "ScrollButton" (prompt-kit.com, MIT).
// Built on use-stick-to-bottom: follows a streaming reply while you're at the
// bottom, stops following as soon as you scroll up, and offers a way back down.
// Changes: JS instead of TS; the root is a positioning box (the library makes
// the inner element scroll), the scroll button uses the shared Button, and
// ChatContainerFollow re-attaches to the bottom whenever the user sends.
import { useEffect } from "react";
import { ArrowDown } from "lucide-react";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function ChatContainerRoot({ children, className, ...props }) {
  return (
    <StickToBottom
      className={cn("relative flex min-h-0 overflow-hidden", className)}
      resize="smooth"
      initial="instant"
      role="log"
      {...props}
    >
      {children}
    </StickToBottom>
  );
}

function ChatContainerContent({ children, className, ...props }) {
  return (
    <StickToBottom.Content className={cn("flex w-full flex-col", className)} {...props}>
      {children}
    </StickToBottom.Content>
  );
}

function ScrollButton({ className, ...props }) {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();

  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label="Jump to latest message"
      tabIndex={isAtBottom ? -1 : 0}
      aria-hidden={isAtBottom}
      className={cn(
        "rounded-full transition-[opacity,transform] duration-200 ease-out",
        isAtBottom ? "pointer-events-none translate-y-3 opacity-0" : "translate-y-0 opacity-100",
        className
      )}
      onClick={() => scrollToBottom()}
      {...props}
    >
      <ArrowDown />
    </Button>
  );
}

// Jump back to the latest message whenever `signal` changes (e.g. a new user message).
function ChatContainerFollow({ signal }) {
  const { scrollToBottom } = useStickToBottomContext();

  useEffect(() => {
    scrollToBottom({ animation: "smooth", ignoreEscapes: true });
  }, [signal, scrollToBottom]);

  return null;
}

export { ChatContainerRoot, ChatContainerContent, ChatContainerFollow, ScrollButton };
