import { useCallback, useRef, useState } from "react";
import { AnimatePresence, LazyMotion, MotionConfig, domAnimation, m, useReducedMotion } from "motion/react";
import {
  ChevronDown,
  Club,
  Diamond,
  Heart,
  ImagePlus,
  Menu,
  MessageSquareText,
  PanelLeftClose,
  PanelLeftOpen,
  RotateCcw,
  Send,
  Spade,
  X,
} from "lucide-react";
import { useChat } from "./hooks/useChat";
import ChatMessage from "./components/ChatMessage";
import GameStateCard from "./components/GameStateCard";
import ImageUploader, { addImageFiles, useClipboardImages } from "./components/ImageUploader";
import { Button } from "@/components/ui/button";
import {
  ChatContainerContent,
  ChatContainerFollow,
  ChatContainerRoot,
  ScrollButton,
} from "@/components/ui/chat-container";
import { Disclosure, DisclosureContent } from "@/components/ui/disclosure";
import { PromptInput, PromptInputActions, PromptInputTextarea } from "@/components/ui/prompt-input";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { SPRING, dealIn } from "@/lib/motion";
import { cn } from "@/lib/utils";

const QUICK_PROMPTS = [
  "How do I arrange my jokers here?",
  "Analyze the highest score I can get here.",
  "What's the best buy in this shop?",
  "Can this line survive the next blind?",
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

const SIDEBAR_WIDTH = 320;
const SIDEBAR_GAP = 20;

function SidebarPanel({ gameState, handSettings, updateHandSetting, mobile = false }) {
  const state = gameState ?? EMPTY_GAME_STATE;
  const Title = mobile ? SheetTitle : "h2";
  const Description = mobile ? SheetDescription : "p";

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="px-5 pt-5">
        <div className="flex items-center justify-between gap-3">
          <Title className="panel-label text-gold">Game State</Title>
          <div className="flex items-center gap-2">
            {state.screen_type ? (
              <span className="status-pill">
                <span className="status-light" aria-hidden="true" />
                <span className="pixel-font text-[12px] text-ink">{state.screen_type}</span>
              </span>
            ) : null}
            {mobile ? (
              <SheetClose asChild>
                <Button size="icon-sm" aria-label="Close game state panel">
                  <X />
                </Button>
              </SheetClose>
            ) : null}
          </div>
        </div>
        <Description className="terminal-copy mt-3 text-[12px] leading-6 text-ink-muted">
          Quick reminders, synergy targets, and hand values update here as screenshots are analyzed.
        </Description>
      </div>
      <div className="mt-3 min-h-0 flex-1 overflow-y-auto border-t-2 border-white/[0.06] px-5 pb-5 pt-2">
        <GameStateCard state={state} handSettings={handSettings} updateHandSetting={updateHandSetting} />
      </div>
    </div>
  );
}

function SuitMark() {
  return (
    <div
      className="hidden h-12 w-12 shrink-0 items-center justify-center rounded-control border-2 border-line bg-black/40 sm:flex"
      aria-hidden="true"
    >
      <div className="grid grid-cols-2 gap-1">
        <Spade className="h-3.5 w-3.5 text-gold" />
        <Heart className="h-3.5 w-3.5 text-suit-heart" />
        <Club className="h-3.5 w-3.5 text-felt-glow" />
        <Diamond className="h-3.5 w-3.5 text-sky" />
      </div>
    </div>
  );
}

function MessageList({ items, staggered = false }) {
  const reduceMotion = useReducedMotion();

  return items.map((message, index) => (
    <m.div
      key={message.id}
      initial={reduceMotion ? false : dealIn.initial}
      animate={dealIn.animate}
      transition={{ ...SPRING, delay: staggered ? 0.12 + index * 0.08 : 0 }}
    >
      <ChatMessage
        role={message.role}
        content={message.content}
        streaming={message.streaming}
        imagePreviews={message.imagePreviews}
      />
    </m.div>
  ));
}

export default function App() {
  const { messages, gameState, handSettings, isLoading, sendMessage, updateHandSetting, clearChat } = useChat();
  const [input, setInput] = useState("");
  const [imageFiles, setImageFiles] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarVisible, setSidebarVisible] = useState(true);
  const [attachmentsOpen, setAttachmentsOpen] = useState(false);
  const [promptsOpen, setPromptsOpen] = useState(false);
  const textareaRef = useRef(null);
  const reduceMotion = useReducedMotion();

  const handlePastedImages = useCallback((pasted) => {
    setImageFiles((current) => addImageFiles(current, pasted) ?? current);
    setAttachmentsOpen(true);
  }, []);
  useClipboardImages(handlePastedImages);

  const handlePrompt = (prompt) => {
    setInput(prompt);
    textareaRef.current?.focus();
  };

  const canSend = !isLoading && (input.trim().length > 0 || imageFiles.length > 0);

  const handleSend = () => {
    if (!canSend) return;
    const text = input.trim();

    sendMessage(text || "(screenshots uploaded - please analyse my game state)", imageFiles);
    setInput("");
    setImageFiles([]);
    setAttachmentsOpen(false);
  };

  const isEmpty = messages.length === 0;
  const userMessageCount = messages.filter((message) => message.role === "user").length;

  return (
    <LazyMotion features={domAnimation} strict>
      <MotionConfig reducedMotion="user" transition={SPRING}>
        <div className="relative h-[100dvh] overflow-hidden text-ink">
          <a
            href="#composer-input"
            className="action-button action-button-primary sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50"
            onClick={(event) => {
              event.preventDefault();
              textareaRef.current?.focus();
            }}
          >
            Skip to message box
          </a>
          <div className="vignette-overlay pointer-events-none absolute inset-0" />

          <div className="relative flex h-full xl:p-5">
            <AnimatePresence initial={false}>
              {sidebarVisible ? (
                <m.aside
                  key="sidebar"
                  id="game-state-sidebar"
                  aria-label="Game state"
                  className="hidden shrink-0 overflow-hidden xl:block"
                  initial={{ width: 0, opacity: 0 }}
                  animate={{ width: SIDEBAR_WIDTH + SIDEBAR_GAP, opacity: 1 }}
                  exit={{ width: 0, opacity: 0 }}
                  transition={reduceMotion ? { duration: 0 } : SPRING}
                >
                  <div className="terminal-shell h-full overflow-hidden" style={{ width: SIDEBAR_WIDTH }}>
                    <SidebarPanel
                      gameState={gameState}
                      handSettings={handSettings}
                      updateHandSetting={updateHandSetting}
                    />
                  </div>
                </m.aside>
              ) : null}
            </AnimatePresence>

            <m.main
              className="terminal-shell flex min-w-0 flex-1 flex-col overflow-hidden rounded-none border-0 xl:rounded-shell xl:border-2"
              initial={reduceMotion ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <header className="flex items-center justify-between gap-3 border-b-2 border-white/[0.06] bg-black/20 px-3 py-3 sm:px-6 sm:py-4">
                <div className="flex min-w-0 items-center gap-3 sm:gap-4">
                  <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
                    <SheetTrigger asChild>
                      <Button size="icon" className="xl:hidden" aria-label="Open game state panel">
                        <Menu />
                      </Button>
                    </SheetTrigger>
                    <SheetContent side="left" className="mobile-sheet w-[92vw] max-w-[360px]">
                      <SidebarPanel
                        gameState={gameState}
                        handSettings={handSettings}
                        updateHandSetting={updateHandSetting}
                        mobile
                      />
                    </SheetContent>
                  </Sheet>

                  <Button
                    className="hidden xl:inline-flex"
                    aria-controls="game-state-sidebar"
                    aria-expanded={sidebarVisible}
                    onClick={() => setSidebarVisible((value) => !value)}
                  >
                    {sidebarVisible ? <PanelLeftClose /> : <PanelLeftOpen />}
                    {sidebarVisible ? "Hide Sidebar" : "Show Sidebar"}
                  </Button>

                  <SuitMark />

                  <div className="min-w-0">
                    <h1 className="pixel-font truncate text-[24px] text-gold sm:text-[32px]">Balatro Coach</h1>
                    <p className="terminal-copy mt-1.5 hidden max-w-2xl truncate text-[12px] text-ink-muted sm:block">
                      Coaching for blind survival, shop choices, score math, and joker order.
                    </p>
                  </div>
                </div>

                <div className="flex shrink-0 items-center gap-2 sm:gap-3">
                  <span className={cn("status-pill", isLoading && "status-live")} role="status">
                    <span className="status-light" aria-hidden="true" />
                    <span className="pixel-font sr-only text-[12px] text-ink sm:not-sr-only">
                      {isLoading ? "Thinking" : "Ready"}
                    </span>
                  </span>

                  <AnimatePresence initial={false}>
                    {messages.length > 0 ? (
                      <m.div
                        key="clear"
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.9 }}
                      >
                        <Button variant="danger" size="icon" className="sm:hidden" onClick={clearChat} aria-label="Clear chat">
                          <RotateCcw />
                        </Button>
                        <Button variant="danger" className="hidden sm:inline-flex" onClick={clearChat}>
                          <RotateCcw />
                          Clear Chat
                        </Button>
                      </m.div>
                    ) : null}
                  </AnimatePresence>
                </div>
              </header>

              <ChatContainerRoot key={isEmpty ? "intro" : "conversation"} className="flex-1">
                <ChatContainerFollow signal={userMessageCount} />
                <ChatContainerContent className="mx-auto max-w-[920px] gap-5 px-3 py-5 sm:px-6 lg:px-8">
                  {isEmpty ? <MessageList items={STARTER_MESSAGES} staggered /> : <MessageList items={messages} />}
                </ChatContainerContent>
                <div className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center">
                  <ScrollButton className="pointer-events-auto" />
                </div>
              </ChatContainerRoot>

              <div className="border-t-2 border-white/[0.06] bg-black/20 px-3 pb-3 pt-3 sm:px-6 lg:px-8">
                <div className="mx-auto max-w-[920px]">
                  <PromptInput
                    value={input}
                    onValueChange={setInput}
                    onSubmit={handleSend}
                    isLoading={isLoading}
                    textareaRef={textareaRef}
                    maxHeight={200}
                  >
                    <PromptInputTextarea
                      id="composer-input"
                      aria-label="Ask the coach"
                      placeholder="Ask for the best line, highest score, joker order, or shop decision..."
                    />

                    <PromptInputActions className="justify-between px-1 pb-1 pt-2">
                      <div className="flex min-w-0 items-center gap-2">
                        <Button
                          size="sm"
                          className="is-toggle"
                          aria-expanded={attachmentsOpen}
                          aria-controls="composer-screenshots"
                          onClick={() => setAttachmentsOpen((value) => !value)}
                        >
                          <ImagePlus className="text-gold" />
                          <span className="hidden min-[400px]:inline">Screenshots</span>
                          <span className="sr-only min-[400px]:hidden">Screenshots</span>
                          {imageFiles.length > 0 ? <span className="button-count">{imageFiles.length}</span> : null}
                          <ChevronDown
                            className={cn("transition-transform duration-200 ease-out", attachmentsOpen && "rotate-180")}
                            aria-hidden="true"
                          />
                        </Button>

                        <Button
                          size="sm"
                          className="is-toggle"
                          aria-expanded={promptsOpen}
                          aria-controls="composer-prompts"
                          onClick={() => setPromptsOpen((value) => !value)}
                        >
                          <MessageSquareText className="text-sky" />
                          Quick Prompts
                          <ChevronDown
                            className={cn("transition-transform duration-200 ease-out", promptsOpen && "rotate-180")}
                            aria-hidden="true"
                          />
                        </Button>
                      </div>

                      <Button
                        variant="primary"
                        size="sm"
                        onClick={handleSend}
                        disabled={!canSend}
                        aria-label={isLoading ? "Sending" : "Send"}
                      >
                        <Send />
                        <span className="hidden sm:inline">{isLoading ? "Sending" : "Send"}</span>
                      </Button>
                    </PromptInputActions>

                    <Disclosure open={attachmentsOpen} id="composer-screenshots">
                      <DisclosureContent>
                        <div className="px-1 pb-1 pt-2">
                          <ImageUploader files={imageFiles} onFilesChange={setImageFiles} disabled={isLoading} />
                        </div>
                      </DisclosureContent>
                    </Disclosure>

                    <Disclosure open={promptsOpen} id="composer-prompts">
                      <DisclosureContent>
                        <ul className="flex flex-wrap gap-2 px-1 pb-1 pt-2" aria-label="Quick prompts">
                          {QUICK_PROMPTS.map((prompt) => (
                            <li key={prompt}>
                              <button type="button" className="prompt-chip terminal-copy" onClick={() => handlePrompt(prompt)}>
                                {prompt}
                              </button>
                            </li>
                          ))}
                        </ul>
                      </DisclosureContent>
                    </Disclosure>
                  </PromptInput>
                </div>
              </div>
            </m.main>
          </div>
        </div>
      </MotionConfig>
    </LazyMotion>
  );
}
