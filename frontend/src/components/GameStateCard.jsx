import { useRef, useState } from "react";
import { ChevronDown, CircleHelp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Disclosure, DisclosureContent, DisclosureTrigger } from "@/components/ui/disclosure";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
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

const EDITION_CLASS = {
  foil: "bg-[#4a90d9]/20 text-[#9fd0f7]",
  holographic: "bg-[#9b59b6]/20 text-[#dcb8fb]",
  polychrome: "bg-[#e67e22]/20 text-[#ffbf70]",
  negative: "bg-white/10 text-ink-muted",
};

const HAND_HELP = [
  "Level — planet cards applied to this hand type. Each level boosts base chips × mult.",
  "Times played — how many times you've played this hand this run. Jokers like Observatory, Constellation, and Wee Joker scale with this count.",
  "Chips × mult shown are base values before card chips or joker effects.",
];

// ─────────────────────────────────────────────────────────────────────────────

export default function GameStateCard({ state, handSettings, updateHandSetting }) {
  if (!state) return null;

  const sidebar = state.sidebar ?? {};
  const reminders = sidebar.reminders ?? [];
  const synergyTargets = sidebar.synergy_targets ?? [];
  const jokers = state.jokers ?? [];
  const resources = state.resources ?? {};

  const hasSummary =
    state.ante != null ||
    state.confidence != null ||
    state.low_confidence ||
    resources.hands != null ||
    resources.discards != null ||
    resources.money != null;

  return (
    <div className="divide-y-2 divide-white/[0.06]">
      {hasSummary ? (
        <div className="flex flex-wrap gap-2 pb-4">
          {state.ante != null ? <Stat label="Ante" value={state.ante} /> : null}
          {state.confidence != null ? (
            <Stat value={`${Math.round((state.confidence ?? 0) * 100)}%`} suffix="read" />
          ) : null}
          {state.low_confidence ? <Stat tone="red" label="Low confidence" /> : null}
          {resources.hands != null ? <Stat label="Hands" value={resources.hands} /> : null}
          {resources.discards != null ? <Stat label="Discards" value={resources.discards} /> : null}
          {resources.money != null ? <Stat tone="gold" value={`$${resources.money}`} /> : null}
        </div>
      ) : null}

      <Section title="Run Brief">
        <ul className="space-y-2">
          {reminders.map((item) => (
            <Bullet key={item} className="text-ink-muted" pip="bg-gold">
              {item}
            </Bullet>
          ))}
        </ul>
      </Section>

      <Section title="Jokers To Watch">
        {jokers.length > 0 ? (
          <ul className="mb-4 space-y-1.5">
            {jokers.map((joker, i) => (
              <li key={`${joker.name}-${i}`} className="terminal-copy flex items-center gap-2 text-[12px] leading-6 text-ink">
                <span className="h-1.5 w-1.5 shrink-0 rounded-[1px] bg-gold" aria-hidden="true" />
                <span className="min-w-0 truncate">{joker.name ?? "Unknown Joker"}</span>
                {joker.edition && joker.edition !== "base" ? (
                  <span
                    className={cn(
                      "pixel-font shrink-0 rounded-full px-2 py-1 text-[12px]",
                      EDITION_CLASS[joker.edition] ?? EDITION_CLASS.negative
                    )}
                  >
                    {joker.edition}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
        {synergyTargets.length > 0 ? (
          <ul className="space-y-2">
            {synergyTargets.map((item) => (
              <Bullet key={item} className="text-[#d6e8ff]" pip="bg-sky">
                {item}
              </Bullet>
            ))}
          </ul>
        ) : null}
      </Section>

      <Section title="Hand Settings" defaultOpen help={HAND_HELP}>
        <ul className="divide-y divide-white/[0.06]">
          {(handSettings ?? []).map((hand, index) => (
            <HandRow
              key={hand.name}
              hand={hand}
              onLevelChange={(delta) => updateHandSetting?.(index, "level", delta)}
              onTimesPlayedChange={(delta) => updateHandSetting?.(index, "times_played", delta)}
            />
          ))}
        </ul>
      </Section>
    </div>
  );
}

function Stat({ label, value, suffix, tone = "default" }) {
  return (
    <Badge tone={tone} className="terminal-copy gap-1.5">
      {label ? <span className={value != null ? "text-ink-muted" : undefined}>{label}</span> : null}
      {value != null ? <span className="font-semibold tabular-nums">{value}</span> : null}
      {suffix ? <span className="text-ink-muted">{suffix}</span> : null}
    </Badge>
  );
}

function Bullet({ children, className, pip }) {
  return (
    <li className={cn("terminal-copy flex gap-2.5 text-[12px] leading-6", className)}>
      <span className={cn("mt-[9px] h-1.5 w-1.5 shrink-0 rounded-[1px]", pip)} aria-hidden="true" />
      <span>{children}</span>
    </li>
  );
}

function NumberField({ label, value, onChange, onCommit, className }) {
  return (
    <label className="flex items-center gap-2">
      <span className="pixel-font text-[12px] text-ink-subtle" aria-hidden="true">
        {label.short}
      </span>
      <input
        type="text"
        inputMode="numeric"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onCommit}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
        }}
        aria-label={label.full}
        className={cn("hand-input pixel-font text-[14px]", className)}
      />
    </label>
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

  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2 py-2.5">
      <p className="flex min-w-0 items-baseline gap-2">
        <span className="terminal-copy truncate text-[12px] font-semibold leading-5 text-ink">{hand.name}</span>
        <span className="pixel-font shrink-0 text-[12px] text-ink-subtle">{planet}</span>
      </p>

      <p className="flex items-center gap-1.5" aria-label={`${stats.chips} chips times ${stats.mult} mult`}>
        <span className="score-chip bg-chips">{stats.chips}</span>
        <span className="pixel-font text-[12px] text-ink-subtle" aria-hidden="true">
          ×
        </span>
        <span className="score-chip bg-mult">{stats.mult}</span>
      </p>

      <div className="col-span-2 flex items-center gap-5">
        <NumberField
          label={{ short: "Lvl", full: `${hand.name} level` }}
          value={levelStr}
          onChange={setLevelStr}
          onCommit={commitLevel}
          className={isLeveled ? "border-gold/60 text-gold" : "text-ink-muted"}
        />
        <NumberField
          label={{ short: "Played", full: `${hand.name} times played` }}
          value={playedStr}
          onChange={setPlayedStr}
          onCommit={commitPlayed}
          className="text-suit-diamond"
        />
      </div>
    </li>
  );
}

function Section({ title, defaultOpen = false, help, children }) {
  return (
    <Disclosure open={defaultOpen} className="py-2">
      <div className="-mx-2 flex items-center gap-1">
        <DisclosureTrigger>
          <button type="button" className="section-trigger">
            <span className="panel-label">{title}</span>
            <ChevronDown className="h-4 w-4" aria-hidden="true" />
          </button>
        </DisclosureTrigger>
        {help ? (
          <Popover>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-control text-ink-subtle transition-colors duration-200 ease-out hover:bg-white/5 hover:text-ink"
                aria-label={`How ${title.toLowerCase()} work`}
              >
                <CircleHelp className="h-4 w-4" />
              </button>
            </PopoverTrigger>
            <PopoverContent>
              <ul className="terminal-copy space-y-2">
                {help.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </PopoverContent>
          </Popover>
        ) : null}
      </div>
      <DisclosureContent>
        <div className="pb-3 pt-2">{children}</div>
      </DisclosureContent>
    </Disclosure>
  );
}
