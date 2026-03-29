import { useEffect, useState } from "react";
import { ChevronDown, Minus, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export default function GameStateCard({ state }) {
  if (!state) return null;

  const sidebar = state.sidebar ?? {};
  const reminders = sidebar.reminders ?? [];
  const synergyTargets = sidebar.synergy_targets ?? [];
  const [handSettings, setHandSettings] = useState(sidebar.hand_settings ?? []);
  const [openSections, setOpenSections] = useState({
    brief: true,
    jokers: true,
    hands: true,
  });

  useEffect(() => {
    setHandSettings(sidebar.hand_settings ?? []);
  }, [sidebar.hand_settings]);

  const toggleSection = (key) => {
    setOpenSections((current) => ({ ...current, [key]: !current[key] }));
  };

  const updateHandValue = (index, field, delta) => {
    setHandSettings((current) =>
      current.map((hand, handIndex) => {
        if (handIndex !== index) return hand;
        const nextValue = Math.max(0, Number(hand[field] ?? 0) + delta);
        return { ...hand, [field]: nextValue };
      })
    );
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
        <div className="space-y-2">
          {handSettings.map((hand, index) => (
            <div
              key={hand.name}
              className="rounded-[14px] border border-white/10 bg-black/18 px-3 py-2"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="terminal-copy truncate text-[12px] font-medium text-[#edf2ef]">
                    {hand.name}
                  </p>
                  <p className="pixel-font mt-1 text-[10px] text-[#9aa9a0]">Lvl {hand.level}</p>
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  <ValueStepper
                    colorClass="border-[#3498db]/55 bg-[#3498db]/16 text-[#d9efff]"
                    value={hand.chips}
                    onDecrease={() => updateHandValue(index, "chips", -5)}
                    onIncrease={() => updateHandValue(index, "chips", 5)}
                  />
                  <ValueStepper
                    colorClass="border-[#e43f3f]/55 bg-[#e43f3f]/16 text-[#ffd7d7]"
                    prefix="x"
                    value={hand.mult}
                    onDecrease={() => updateHandValue(index, "mult", -1)}
                    onIncrease={() => updateHandValue(index, "mult", 1)}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </Section>
    </div>
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

function ValueStepper({ value, prefix = "", colorClass, onDecrease, onIncrease }) {
  return (
    <div className={cn("flex items-center gap-1 rounded-full border px-1.5 py-1", colorClass)}>
      <button
        type="button"
        className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-white/10 bg-black/20"
        onClick={onDecrease}
        aria-label="Decrease value"
      >
        <Minus className="h-3 w-3" />
      </button>
      <span className="pixel-font min-w-[36px] text-center text-[10px]">
        {prefix}
        {value}
      </span>
      <button
        type="button"
        className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-white/10 bg-black/20"
        onClick={onIncrease}
        aria-label="Increase value"
      >
        <Plus className="h-3 w-3" />
      </button>
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
