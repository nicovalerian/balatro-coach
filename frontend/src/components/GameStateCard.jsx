import { useRef, useState } from "react";
import { ChevronDown, HelpCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

// ── Planet card scaling table (mirrors backend hand_eval.py) ─────────────────
// Source: https://balatrogame.fandom.com/wiki/Planet_Cards
const HAND_STATS = {
  "High Card":        { baseChips: 5,   baseMult: 1,  chipsPerLevel: 10, multPerLevel: 1,  planet: "Pluto" },
  "Pair":             { baseChips: 10,  baseMult: 2,  chipsPerLevel: 15, multPerLevel: 1,  planet: "Mercury" },
  "Two Pair":         { baseChips: 20,  baseMult: 2,  chipsPerLevel: 20, multPerLevel: 1,  planet: "Uranus" },
  "Three of a Kind":  { baseChips: 30,  baseMult: 3,  chipsPerLevel: 20, multPerLevel: 2,  planet: "Venus" },
  "Straight":         { baseChips: 30,  baseMult: 4,  chipsPerLevel: 30, multPerLevel: 3,  planet: "Earth" },
  "Flush":            { baseChips: 35,  baseMult: 4,  chipsPerLevel: 15, multPerLevel: 2,  planet: "Jupiter" },
  "Full House":       { baseChips: 40,  baseMult: 4,  chipsPerLevel: 25, multPerLevel: 2,  planet: "Saturn" },
  "Four of a Kind":   { baseChips: 60,  baseMult: 7,  chipsPerLevel: 30, multPerLevel: 3,  planet: "Mars" },
  "Straight Flush":   { baseChips: 100, baseMult: 8,  chipsPerLevel: 40, multPerLevel: 4,  planet: "Neptune" },
  "Royal Flush":      { baseChips: 100, baseMult: 8,  chipsPerLevel: 40, multPerLevel: 4,  planet: "Planet X" },
  "Five of a Kind":   { baseChips: 120, baseMult: 12, chipsPerLevel: 35, multPerLevel: 3,  planet: "Eris" },
  "Flush House":      { baseChips: 140, baseMult: 14, chipsPerLevel: 40, multPerLevel: 4,  planet: "Ceres" },
  "Flush Five":       { baseChips: 160, baseMult: 16, chipsPerLevel: 50, multPerLevel: 3,  planet: "Black Hole" },
};

function computeHandStats(name, level) {
  const s = HAND_STATS[name];
  if (!s) return { chips: "?", mult: "?" };
  const bonus = Math.max(0, level - 1);
  return {
    chips: s.baseChips + bonus * s.chipsPerLevel,
    mult: s.baseMult + bonus * s.multPerLevel,
  };
}

// ─────────────────────────────────────────────────────────────────────────────

export default function GameStateCard({ state, handSettings, updateHandSetting }) {
  if (!state) return null;

  const sidebar = state.sidebar ?? {};
  const reminders = sidebar.reminders ?? [];
  const synergyTargets = sidebar.synergy_targets ?? [];
  const [openSections, setOpenSections] = useState({
    brief: false,
    jokers: false,
    hands: true,
  });

  const toggleSection = (key) => {
    setOpenSections((current) => ({ ...current, [key]: !current[key] }));
  };

  return (
    <div className="space-y-4">
      <div className="terminal-inset px-4 py-4">
        <div className="flex flex-wrap gap-2">
          <InfoBadge tone="gold">{state.screen_type ?? "unknown"}</InfoBadge>
          {state.ante != null ? <InfoBadge>Ante {state.ante}</InfoBadge> : null}
          {state.confidence != null ? (
            <InfoBadge>{Math.round((state.confidence ?? 0) * 100)}% read</InfoBadge>
          ) : null}
          {state.low_confidence ? <InfoBadge tone="red">Low confidence</InfoBadge> : null}
        </div>

        {(state.resources?.hands != null ||
          state.resources?.discards != null ||
          state.resources?.money != null) ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {state.resources?.hands != null ? (
              <InfoBadge>Hands {state.resources.hands}</InfoBadge>
            ) : null}
            {state.resources?.discards != null ? (
              <InfoBadge>Discards {state.resources.discards}</InfoBadge>
            ) : null}
            {state.resources?.money != null ? (
              <InfoBadge tone="gold">${state.resources.money}</InfoBadge>
            ) : null}
          </div>
        ) : null}
      </div>

      <Section
        title="Run Brief"
        open={openSections.brief}
        onToggle={() => toggleSection("brief")}
      >
        <ul className="space-y-2">
          {reminders.map((item) => (
            <li key={item} className="terminal-copy flex gap-2 text-[12px] leading-6 text-[#dce3de]">
              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#f2c237]" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section
        title="Jokers To Watch"
        open={openSections.jokers}
        onToggle={() => toggleSection("jokers")}
      >
        <ul className="space-y-2">
          {synergyTargets.map((item) => (
            <li key={item} className="terminal-copy flex gap-2 text-[12px] leading-6 text-[#d6e8ff]">
              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#3498db]" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section
        title="Hand Settings"
        open={openSections.hands}
        onToggle={() => toggleSection("hands")}
        helpText={
          "Level — planet cards applied to this hand type. Each level boosts base chips × mult.\n\n" +
          "Times played — how many times you've played this hand this run. " +
          "Jokers like Observatory, Constellation, and Wee Joker scale with this count.\n\n" +
          "Chips × mult shown are base values before card chips or joker effects."
        }
      >
        <div className="space-y-1.5">
          {(handSettings ?? []).map((hand, index) => (
            <HandRow
              key={hand.name}
              hand={hand}
              onLevelChange={(delta) => updateHandSetting?.(index, "level", delta)}
              onTimesPlayedChange={(delta) => updateHandSetting?.(index, "times_played", delta)}
            />
          ))}
        </div>
      </Section>
    </div>
  );
}

function HandRow({ hand, onLevelChange, onTimesPlayedChange }) {
  const stats = computeHandStats(hand.name, hand.level);
  const planet = HAND_STATS[hand.name]?.planet ?? "";
  const isLeveled = hand.level > 1;

  // Local string state so the user can fully clear and retype
  const [levelStr, setLevelStr] = useState(String(hand.level));
  const [playedStr, setPlayedStr] = useState(String(hand.times_played));

  // Sync when parent value changes (e.g. reset from outside)
  const prevLevelRef = useRef(hand.level);
  if (prevLevelRef.current !== hand.level) {
    prevLevelRef.current = hand.level;
    setLevelStr(String(hand.level));
  }
  const prevPlayedRef = useRef(hand.times_played);
  if (prevPlayedRef.current !== hand.times_played) {
    prevPlayedRef.current = hand.times_played;
    setPlayedStr(String(hand.times_played));
  }

  const commitLevel = () => {
    const next = Math.max(1, parseInt(levelStr, 10) || 1);
    setLevelStr(String(next));
    onLevelChange(next - hand.level);
  };

  const commitPlayed = () => {
    const next = Math.max(0, parseInt(playedStr, 10) || 0);
    setPlayedStr(String(next));
    onTimesPlayedChange(next - hand.times_played);
  };

  const handleKeyDown = (commit) => (e) => {
    if (e.key === "Enter") { e.currentTarget.blur(); commit(); }
  };

  return (
    <div
      className={cn(
        "rounded-[12px] border px-3 py-2 transition-colors",
        isLeveled
          ? "border-white/18 bg-[#1a2e24]/60"
          : "border-white/8 bg-black/18"
      )}
    >
      {/* Top row: name + planet */}
      <div className="mb-1.5 flex items-baseline gap-1.5">
        <span className="terminal-copy text-[11px] font-semibold text-[#edf2ef]">{hand.name}</span>
        <span className="pixel-font text-[9px] text-[#6a8070]">{planet}</span>
      </div>

      {/* Controls row */}
      <div className="flex items-center gap-3">
        {/* Level input */}
        <div className="flex items-center gap-1">
          <span className="pixel-font text-[9px] text-[#6a8070]">lvl</span>
          <input
            type="text"
            inputMode="numeric"
            value={levelStr}
            onChange={(e) => setLevelStr(e.target.value)}
            onBlur={commitLevel}
            onKeyDown={handleKeyDown(commitLevel)}
            aria-label="Hand level"
            className={cn(
              "pixel-font w-9 rounded-full border-0 px-1.5 py-0.5 text-center text-[10px] outline-none",
              isLeveled
                ? "bg-white/90 text-[#1a2a2a] shadow-sm"
                : "bg-white/12 text-[#c8d4ce]"
            )}
          />
        </div>

        {/* Times played input */}
        <div className="flex items-center gap-1">
          <span className="pixel-font text-[9px] text-[#6a8070]">played</span>
          <input
            type="text"
            inputMode="numeric"
            value={playedStr}
            onChange={(e) => setPlayedStr(e.target.value)}
            onBlur={commitPlayed}
            onKeyDown={handleKeyDown(commitPlayed)}
            aria-label="Times played"
            className="pixel-font w-9 rounded-full border-0 bg-[#2a3a30] px-1.5 py-0.5 text-center text-[10px] text-[#ff8f00] outline-none"
          />
          <span className="pixel-font text-[9px] text-[#6a8070]">×</span>
        </div>
      </div>

      {/* Chips × Mult — own line so it never overflows at any sidebar width */}
      <div className="mt-1.5 flex items-center gap-1">
        <span className="pixel-font rounded-full bg-[#009dff] px-2 py-0.5 text-center text-[10px] font-semibold text-white shadow-sm">
          {stats.chips}
        </span>
        <span className="pixel-font text-[9px] text-[#6a8070]">×</span>
        <span className="pixel-font rounded-full bg-[#FE5F55] px-2 py-0.5 text-center text-[10px] font-semibold text-white shadow-sm">
          {stats.mult}
        </span>
      </div>
    </div>
  );
}

function Section({ title, open, onToggle, helpText, children }) {
  return (
    <div className="terminal-inset px-4 py-4">
      <div className="flex items-center gap-1.5">
        <button type="button" className="dropdown-toggle flex-1" onClick={onToggle}>
          <span className="panel-label">{title}</span>
          <ChevronDown
            className={cn("h-4 w-4 transition-transform duration-200", open && "rotate-180")}
          />
        </button>
        {helpText ? (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="inline-flex shrink-0 items-center justify-center rounded text-[#6a8070] transition-colors hover:text-[#c8d4ce]"
                  aria-label="Help"
                >
                  <HelpCircle className="h-3.5 w-3.5" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="left" className="max-w-[220px] whitespace-pre-line text-[11px] leading-[1.5]">
                {helpText}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : null}
      </div>
      <div className={cn("expandable-section mt-3 opacity-100", open && "expandable-section-open")}>
        <div className="expandable-inner">{children}</div>
      </div>
    </div>
  );
}

function InfoBadge({ children, tone = "default" }) {
  return (
    <Badge
      variant="outline"
      className={[
        "rounded-full border px-2.5 py-1.5",
        "terminal-copy text-[12px] text-[#eef2ef]",
        tone === "gold" ? "border-[#f2c237]/60 bg-[#f2c237]/12 text-[#f7db83]" : "",
        tone === "red" ? "border-[#e43f3f]/60 bg-[#e43f3f]/12 text-[#ffc9c9]" : "",
        tone === "default" ? "border-white/12 bg-black/15" : "",
      ].join(" ")}
    >
      {children}
    </Badge>
  );
}
