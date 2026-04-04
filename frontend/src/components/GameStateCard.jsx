import { useState } from "react";
import { ChevronDown, Minus, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
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
    brief: true,
    jokers: true,
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
        title="Game State / Run Brief"
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
        <span className="terminal-copy text-[11px] font-semibold text-[#edf2ef]">
          {hand.name}
        </span>
        <span className="pixel-font text-[9px] text-[#6a8070]">{planet}</span>
      </div>

      {/* Controls row */}
      <div className="flex items-center justify-between gap-2">
        {/* Level stepper */}
        <div className="flex items-center gap-1">
          <StepBtn direction="dec" onClick={onLevelChange} aria-label="Decrease level" />
          <span
            className={cn(
              "pixel-font min-w-[48px] rounded-full px-2 py-0.5 text-center text-[10px]",
              isLeveled
                ? "bg-white/90 text-[#1a2a2a] shadow-sm"
                : "bg-white/12 text-[#c8d4ce]"
            )}
          >
            lvl.{hand.level}
          </span>
          <StepBtn direction="inc" onClick={onLevelChange} aria-label="Increase level" />
        </div>

        {/* Times played stepper */}
        <div className="flex items-center gap-1">
          <StepBtn direction="dec" onClick={onTimesPlayedChange} aria-label="Decrease times played" />
          <span className="pixel-font min-w-[36px] rounded-full bg-[#2a3a30] px-2 py-0.5 text-center text-[10px] text-[#ff8f00]">
            {hand.times_played}×
          </span>
          <StepBtn direction="inc" onClick={onTimesPlayedChange} aria-label="Increase times played" />
        </div>

        {/* Chips × Mult display (read-only, computed from level) */}
        <div className="flex shrink-0 items-center gap-1">
          <span className="pixel-font min-w-[28px] rounded-full bg-[#009dff] px-2 py-0.5 text-center text-[10px] font-semibold text-white shadow-sm">
            {stats.chips}
          </span>
          <span className="pixel-font text-[9px] text-[#6a8070]">×</span>
          <span className="pixel-font min-w-[20px] rounded-full bg-[#FE5F55] px-2 py-0.5 text-center text-[10px] font-semibold text-white shadow-sm">
            {stats.mult}
          </span>
        </div>
      </div>
    </div>
  );
}

function StepBtn({ direction, onClick }) {
  const delta = direction === "inc" ? 1 : -1;
  return (
    <button
      type="button"
      onClick={() => onClick(delta)}
      className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded border border-white/15 bg-[#374244] text-[#9aa9a0] transition-colors hover:border-white/50 hover:text-white active:scale-95"
    >
      {direction === "dec" ? <Minus className="h-2.5 w-2.5" /> : <Plus className="h-2.5 w-2.5" />}
    </button>
  );
}

function Section({ title, open, onToggle, children }) {
  return (
    <div className="terminal-inset px-4 py-4">
      <button type="button" className="dropdown-toggle w-full" onClick={onToggle}>
        <span className="panel-label">{title}</span>
        <ChevronDown
          className={cn("h-4 w-4 transition-transform duration-200", open && "rotate-180")}
        />
      </button>
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
