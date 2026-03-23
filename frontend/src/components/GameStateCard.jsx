/**
 * GameStateCard
 * Renders the structured game-state JSON returned by the CV pipeline
 * in a readable, colour-coded card panel.
 */
export default function GameStateCard({ state }) {
  if (!state) return null;

  const suitSymbol = { Spades: "♠", Hearts: "♥", Clubs: "♣", Diamonds: "♦" };
  const suitColor = { Spades: "#a8b4f8", Hearts: "#f87171", Clubs: "#86efac", Diamonds: "#fbbf24" };

  return (
    <div style={styles.card}>
      {/* Header */}
      <div style={styles.header}>
        <span style={styles.screenBadge}>{state.screen_type ?? "unknown"}</span>
        {state.low_confidence && (
          <span style={styles.warnBadge}>⚠ low confidence</span>
        )}
        {state.ante && <span style={styles.metaBadge}>Ante {state.ante}</span>}
      </div>

      <div style={styles.grid}>
        {/* Resources */}
        {Object.keys(state.resources ?? {}).length > 0 && (
          <Section title="Resources">
            <div style={styles.chipRow}>
              {state.resources.hands != null && <Chip icon="🤚" label={`${state.resources.hands} hands`} color="#818cf8" />}
              {state.resources.discards != null && <Chip icon="🗑" label={`${state.resources.discards} discards`} color="#f97316" />}
              {state.resources.money != null && <Chip icon="$" label={`$${state.resources.money}`} color="#4ade80" />}
            </div>
          </Section>
        )}

        {/* Blind */}
        {state.blind?.target && (
          <Section title="Blind">
            <span style={styles.scoreNum}>
              {state.blind.name && <>{state.blind.name} · </>}
              {state.blind.target.toLocaleString()} chips
            </span>
          </Section>
        )}

        {/* Score */}
        {state.score?.current != null && (
          <Section title="Score">
            <span style={styles.scoreNum}>{state.score.current.toLocaleString()}</span>
          </Section>
        )}

        {/* Jokers */}
        {state.jokers?.length > 0 && (
          <Section title={`Jokers (${state.jokers.length})`} fullWidth>
            <div style={styles.tagRow}>
              {state.jokers.map((j, i) => (
                <span key={i} style={styles.jokerTag}>{j.name || `Joker ${i + 1}`}</span>
              ))}
            </div>
          </Section>
        )}

        {/* Hand */}
        {state.hand?.length > 0 && (
          <Section title={`Hand (${state.hand.length})`} fullWidth>
            <div style={styles.cardRow}>
              {state.hand.map((c, i) => {
                const suit = c.suit;
                const color = suitColor[suit] ?? "#e2e8f0";
                const sym = suitSymbol[suit] ?? "?";
                return (
                  <span key={i} style={{ ...styles.playingCard, borderColor: color }}>
                    <span style={{ color, fontSize: 11 }}>{sym}</span>
                    {" "}{c.rank ?? "?"}
                  </span>
                );
              })}
            </div>
          </Section>
        )}

        {/* Consumables */}
        {state.consumables?.length > 0 && (
          <Section title="Consumables" fullWidth>
            <div style={styles.tagRow}>
              {state.consumables.map((c, i) => (
                <span key={i} style={styles.consumableTag}>
                  {c.type === "tarot" ? "🌙" : c.type === "planet" ? "🪐" : "✨"} {c.name || c.type}
                </span>
              ))}
            </div>
          </Section>
        )}

        {/* Shop */}
        {state.shop?.items?.length > 0 && (
          <Section title={`Shop (${state.shop.items.length} items)`} fullWidth>
            <div style={styles.tagRow}>
              {state.shop.items.map((item, i) => (
                <span key={i} style={styles.shopTag}>
                  {item.type === "joker" ? "🃏" : item.type === "tarot" ? "🌙" : item.type === "planet" ? "🪐" : "✨"} {item.name || item.type}
                </span>
              ))}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}

function Section({ title, children, fullWidth }) {
  return (
    <div style={{ ...styles.section, ...(fullWidth ? styles.fullWidth : {}) }}>
      <div style={styles.sectionTitle}>{title}</div>
      {children}
    </div>
  );
}

function Chip({ icon, label, color }) {
  return (
    <span style={{ ...styles.chip, borderColor: color, color }}>
      {icon} {label}
    </span>
  );
}

const styles = {
  card: {
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 12,
    padding: "12px 14px",
    fontSize: 13,
    color: "#e2e8f0",
    marginBottom: 8,
  },
  header: {
    display: "flex",
    gap: 8,
    alignItems: "center",
    marginBottom: 10,
    flexWrap: "wrap",
  },
  screenBadge: {
    background: "#4f46e5",
    color: "#c7d2fe",
    borderRadius: 6,
    padding: "2px 8px",
    fontSize: 12,
    fontWeight: 500,
    textTransform: "capitalize",
  },
  warnBadge: {
    background: "rgba(251,191,36,0.15)",
    color: "#fbbf24",
    borderRadius: 6,
    padding: "2px 8px",
    fontSize: 12,
  },
  metaBadge: {
    background: "rgba(255,255,255,0.08)",
    color: "#94a3b8",
    borderRadius: 6,
    padding: "2px 8px",
    fontSize: 12,
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 8,
  },
  section: {
    background: "rgba(0,0,0,0.2)",
    borderRadius: 8,
    padding: "8px 10px",
  },
  fullWidth: { gridColumn: "1 / -1" },
  sectionTitle: {
    fontSize: 11,
    color: "#64748b",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    marginBottom: 5,
    fontWeight: 500,
  },
  chipRow: { display: "flex", gap: 6, flexWrap: "wrap" },
  chip: {
    border: "1px solid",
    borderRadius: 6,
    padding: "2px 8px",
    fontSize: 12,
    background: "rgba(0,0,0,0.2)",
  },
  scoreNum: { fontSize: 16, fontWeight: 600, color: "#f0f9ff" },
  tagRow: { display: "flex", gap: 5, flexWrap: "wrap" },
  jokerTag: {
    background: "rgba(139,92,246,0.2)",
    border: "1px solid rgba(139,92,246,0.4)",
    color: "#c4b5fd",
    borderRadius: 6,
    padding: "2px 8px",
    fontSize: 12,
  },
  consumableTag: {
    background: "rgba(99,102,241,0.15)",
    border: "1px solid rgba(99,102,241,0.3)",
    color: "#a5b4fc",
    borderRadius: 6,
    padding: "2px 8px",
    fontSize: 12,
  },
  shopTag: {
    background: "rgba(245,158,11,0.12)",
    border: "1px solid rgba(245,158,11,0.3)",
    color: "#fcd34d",
    borderRadius: 6,
    padding: "2px 8px",
    fontSize: 12,
  },
  cardRow: { display: "flex", gap: 5, flexWrap: "wrap" },
  playingCard: {
    background: "rgba(255,255,255,0.06)",
    border: "1px solid",
    borderRadius: 6,
    padding: "3px 8px",
    fontSize: 13,
    fontWeight: 600,
    color: "#f1f5f9",
  },
};
