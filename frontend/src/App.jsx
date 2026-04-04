import { useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  Club,
  Diamond,
  Heart,
  Menu,
  RotateCcw,
  Send,
  Spade,
  X,
} from "lucide-react";
import { useChat } from "./hooks/useChat";
import ChatMessage from "./components/ChatMessage";
import GameStateCard from "./components/GameStateCard";
import ImageUploader from "./components/ImageUploader";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import {
  Sheet,
  SheetContent,
  SheetTrigger,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

const QUICK_PROMPTS = [
  "How do I arrange my jokers here?",
  "Analyze the highest score I can get here.",
  "What's the best buy in this shop?",
  "Can this line survive the next blind?",
];

const COACH_PRIORITIES = [
  {
    label: "Blind First",
    detail: "Beat the next score check before chasing greedier scaling.",
  },
  {
    label: "Economy Tempo",
    detail: "Protect money and rerolls whenever the board gives you room.",
  },
  {
    label: "Joker Order",
    detail: "Left-to-right sequencing matters more than flashy rarity.",
  },
];

const STARTER_MESSAGES = [
  {
    id: "starter-1",
    role: "assistant",
    content:
      "Upload up to **3 screenshots** from your blind, hand, or shop and ask what to do next. I'll help with score math, joker order, shop buys, and survival lines.",
  },
  {
    id: "starter-2",
    role: "user",
    content: "What kind of coaching can you give me?",
  },
  {
    id: "starter-3",
    role: "assistant",
    content:
      "**Recommended use:** ask one concrete question at a time.\n\n- Blind survival and best line this hand\n- Joker order and scoring sequence\n- Shop buys, sells, rerolls, and economy\n- Highest score line from the current board",
  },
];

const EMPTY_GAME_STATE = {
  screen_type: "waiting",
  confidence: null,
  low_confidence: false,
  resources: {},
  sidebar: {
    reminders: [
      "No screenshot analyzed yet.",
      "Upload a blind, hand, or shop view to refresh this panel.",
      "Ask one tactical question at a time.",
    ],
    synergy_targets: [
      "Retriggers for played cards",
      "Right-side xMult finishers",
      "Economy jokers that fund rerolls",
    ],
  },
};

function PromptButton({ prompt, onClick }) {
  return (
    <Button
      type="button"
      variant="ghost"
      className="action-button action-button-ghost min-h-[38px] justify-start px-3 py-2 text-left"
      onClick={() => onClick(prompt)}
    >
      <span className="terminal-copy text-[12px] leading-5 text-inherit">{prompt}</span>
    </Button>
  );
}

function SidebarPanel({ gameState, handSettings, updateHandSetting, mobile = false, onClose }) {
  return (
    <div className="flex h-full flex-col p-4 sm:p-5">
      <section className="terminal-panel flex min-h-0 flex-1 flex-col p-4 sm:p-5">
        <div className="flex items-center justify-between gap-3">
          <p className="panel-label text-primary">Game State / Run Brief</p>
          <div className="flex items-center gap-2">
            {(gameState ?? EMPTY_GAME_STATE)?.screen_type ? (
              <span className="status-pill">
                <span className="status-light" />
                <span className="pixel-font text-[11px] text-white">
                  {(gameState ?? EMPTY_GAME_STATE).screen_type}
                </span>
              </span>
            ) : null}
            {mobile ? (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="action-button action-button-ghost"
                onClick={onClose}
              >
                <X className="h-4 w-4" />
              </Button>
            ) : null}
          </div>
        </div>
        <p className="terminal-copy mt-3 text-[12px] leading-6 text-[#c7d0cb]">
          Quick reminders, synergy targets, and hand values update here as screenshots are analyzed.
        </p>
        <div className="mt-4 min-h-0 flex-1 overflow-y-auto pb-2 pr-1">
          <GameStateCard
            state={gameState ?? EMPTY_GAME_STATE}
            handSettings={handSettings}
            updateHandSetting={updateHandSetting}
          />
        </div>
      </section>
    </div>
  );
}

function EmptyChatState() {
  return (
    <section className="space-y-3 pb-2">
      {STARTER_MESSAGES.map((message) => (
        <ChatMessage key={message.id} role={message.role} content={message.content} />
      ))}
    </section>
  );
}

export default function App() {
  const { messages, gameState, handSettings, isLoading, sendMessage, updateHandSetting, clearChat } = useChat();
  const [input, setInput] = useState("");
  const [imageFiles, setImageFiles] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarVisible, setSidebarVisible] = useState(true);
  const [attachmentsOpen, setAttachmentsOpen] = useState(false);
  const [promptsOpen, setPromptsOpen] = useState(false);
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handlePrompt = (prompt) => {
    setInput(prompt);
    textareaRef.current?.focus();
  };

  const handleSend = () => {
    const text = input.trim();
    if (!text && imageFiles.length === 0) return;

    sendMessage(
      text || "(screenshots uploaded - please analyse my game state)",
      imageFiles
    );
    setInput("");
    setImageFiles([]);
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const isEmpty = messages.length === 0;
  const coachStatus = isLoading ? "Coach Thinking" : "Coach Online";

  return (
    <div className="relative h-[100dvh] overflow-hidden text-foreground">
      <div className="pointer-events-none absolute inset-0 suit-pattern" />
      <div className="pointer-events-none absolute inset-0 scanline-overlay" />
      <div className="pointer-events-none absolute inset-0 vignette-overlay" />

      <div className="relative flex h-full xl:gap-6 xl:p-5">
        <aside
          className={cn(
            "hidden xl:block xl:h-full xl:shrink-0 xl:transition-all xl:duration-200",
            sidebarVisible ? "xl:w-[320px]" : "xl:w-0 xl:overflow-hidden"
          )}
        >
          {sidebarVisible ? (
            <div className="terminal-shell h-full overflow-hidden">
              <SidebarPanel
                gameState={gameState}
                handSettings={handSettings}
                updateHandSetting={updateHandSetting}
              />
            </div>
          ) : null}
        </aside>

        <main className="terminal-shell flex min-w-0 flex-1 flex-col overflow-hidden xl:h-full">
          <header className="border-b border-white/10 bg-black/25 px-4 py-4 sm:px-6">
            <div className="mx-auto flex w-full max-w-[1040px] items-center justify-between gap-4 xl:max-w-none">
              <div className="flex min-w-0 items-center gap-3 sm:gap-4">
                <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
                  <SheetTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="action-button action-button-ghost xl:hidden"
                    >
                      <Menu className="h-4 w-4" />
                    </Button>
                  </SheetTrigger>
                  <SheetContent
                    side="left"
                    className="mobile-sheet w-[92vw] max-w-[360px] p-0"
                    showCloseButton={false}
                  >
                    <SidebarPanel
                      gameState={gameState}
                      handSettings={handSettings}
                      updateHandSetting={updateHandSetting}
                      mobile
                      onClose={() => setSidebarOpen(false)}
                    />
                  </SheetContent>
                </Sheet>

                <Button
                  type="button"
                  variant="ghost"
                  className="action-button action-button-ghost hidden min-h-[44px] px-4 xl:inline-flex"
                  onClick={() => setSidebarVisible((value) => !value)}
                >
                  <Menu className="mr-2 h-4 w-4" />
                  {sidebarVisible ? "Hide Sidebar" : "Show Sidebar"}
                </Button>

                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[16px] border-2 border-white/15 bg-[#0f1316]/85 shadow-[4px_4px_0_rgba(0,0,0,0.55)]">
                  <div className="grid grid-cols-2 gap-1 text-primary">
                    <Spade className="h-3.5 w-3.5" />
                    <Heart className="h-3.5 w-3.5 text-[#e43f3f]" />
                    <Club className="h-3.5 w-3.5 text-[#8af7c8]" />
                    <Diamond className="h-3.5 w-3.5 text-[#3498db]" />
                  </div>
                </div>

                <div className="min-w-0">
                  <p className="pixel-font truncate text-[28px] text-primary sm:text-[32px]">
                    Balatro Coach
                  </p>
                  <p className="terminal-copy mt-1 max-w-2xl text-[12px] text-[#d0d7d2]">
                    Coaching for blind survival, shop choices, score math, and joker order.
                  </p>
                </div>
              </div>

              <div className="flex shrink-0 items-center gap-2 sm:gap-3">
                <span className={cn("status-pill", isLoading && "status-live")}>
                  <span className="status-light" />
                  <span className="pixel-font text-[11px] text-white sm:text-[12px]">
                    {coachStatus}
                  </span>
                </span>

                {messages.length > 0 ? (
                  <Button
                    type="button"
                    className="action-button action-button-danger hidden min-h-[44px] px-4 sm:inline-flex"
                    onClick={clearChat}
                  >
                    <RotateCcw className="mr-2 h-4 w-4" />
                    Clear Chat
                  </Button>
                ) : null}
              </div>
            </div>
          </header>

          <div className="flex min-h-0 flex-1 flex-col">
            <ScrollArea className="min-h-0 flex-1 px-3 py-3 sm:px-5 lg:px-8 lg:py-4">
              <div className="mx-auto w-full max-w-[980px]">
                {isEmpty ? (
                  <EmptyChatState />
                ) : (
                  <div className="space-y-4 pb-4">
                    {messages.map((message, index) => (
                      <div
                        key={message.id}
                        className="message-enter"
                        style={{ animationDelay: `${index * 0.04}s` }}
                      >
                        <ChatMessage
                          role={message.role}
                          content={message.content}
                          streaming={message.streaming}
                          imagePreviews={message.imagePreviews}
                        />
                      </div>
                    ))}
                  </div>
                )}
                <div ref={bottomRef} />
              </div>
            </ScrollArea>

            <div className="border-t border-white/10 bg-gradient-to-t from-black/35 to-transparent px-3 pb-3 pt-2 sm:px-5 lg:px-8 lg:pb-4">
              <div className="mx-auto max-w-[980px]">
                <div className="composer-shell p-2.5 sm:p-3">
                  <div className="flex flex-col gap-2.5">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="pixel-font text-[16px] text-primary">Question</p>
                        <p className="terminal-copy mt-1 text-[12px] text-[#d0d8d3]">
                          Type what you want analyzed, then add screenshots if needed.
                        </p>
                      </div>
                      {imageFiles.length > 0 ? (
                        <span className="status-pill">
                          <span className="status-light" />
                          <span className="pixel-font text-[11px] text-white">
                            {imageFiles.length} screenshot{imageFiles.length > 1 ? "s" : ""}
                          </span>
                        </span>
                      ) : null}
                    </div>

                    <div className="question-shell p-2">
                      <Textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(event) => setInput(event.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask for the best line, highest score, joker order, or shop decision..."
                        rows={2}
                        disabled={isLoading}
                        className="terminal-textarea text-[14px] leading-6"
                      />
                    </div>

                    <div className="grid gap-2.5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
                      <div className="space-y-2">
                        <div className="flex flex-col gap-2 sm:flex-row">
                          <button
                            type="button"
                            className="dropdown-toggle"
                            onClick={() => setAttachmentsOpen((value) => !value)}
                            aria-expanded={attachmentsOpen}
                          >
                            <span className="flex items-center gap-2">
                              <span className="pixel-font text-[12px] text-[#f2c237]">
                                Screenshots
                              </span>
                              {imageFiles.length > 0 ? (
                                <span className="dropdown-count">
                                  {imageFiles.length}
                                </span>
                              ) : null}
                            </span>
                            <ChevronDown
                              className={cn(
                                "h-4 w-4 transition-transform duration-200",
                                attachmentsOpen && "rotate-180"
                              )}
                            />
                          </button>

                          <button
                            type="button"
                            className="dropdown-toggle"
                            onClick={() => setPromptsOpen((value) => !value)}
                            aria-expanded={promptsOpen}
                          >
                            <span className="pixel-font text-[12px] text-[#d9e6f2]">
                              Quick Prompts
                            </span>
                            <ChevronDown
                              className={cn(
                                "h-4 w-4 transition-transform duration-200",
                                promptsOpen && "rotate-180"
                              )}
                            />
                          </button>
                        </div>

                        <div
                          className={cn(
                            "expandable-section",
                            attachmentsOpen && "expandable-section-open"
                          )}
                        >
                          <div className="expandable-inner">
                            <ImageUploader
                              files={imageFiles}
                              onFilesChange={setImageFiles}
                              disabled={isLoading}
                            />
                          </div>
                        </div>

                        <div
                          className={cn(
                            "expandable-section",
                            promptsOpen && "expandable-section-open"
                          )}
                        >
                          <div className="expandable-inner">
                            <div className="flex flex-wrap gap-1.5">
                              {QUICK_PROMPTS.map((prompt) => (
                                <PromptButton
                                  key={prompt}
                                  prompt={prompt}
                                  onClick={handlePrompt}
                                />
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>

                      <Button
                        type="button"
                        className="action-button action-button-primary min-h-[48px] min-w-[120px] px-4 lg:mt-[2px]"
                        onClick={handleSend}
                        disabled={isLoading || (!input.trim() && imageFiles.length === 0)}
                      >
                        <Send className="mr-2 h-4 w-4" />
                        {isLoading ? "Sending" : "Send"}
                      </Button>
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="terminal-copy text-[11px] text-[#a6b1aa]">
                        Enter to send. Shift+Enter for newline. Paste screenshots with Ctrl+V.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
