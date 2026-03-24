/**
 * GameStateCard
 * Renders the structured game-state JSON returned by the CV pipeline
 * in a readable, colour-coded card panel.
 */
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function GameStateCard({ state }) {
  if (!state) return null;

  const suitSymbol = { Spades: "S", Hearts: "H", Clubs: "C", Diamonds: "D" };
  const suitTone = {
    Spades: "border-accent/60 text-accent",
    Hearts: "border-primary/60 text-primary",
    Clubs: "border-secondary/70 text-secondary",
    Diamonds: "border-muted-foreground/50 text-muted-foreground",
  };

  return (
    <Card className="bg-card/80">
      <CardHeader className="space-y-2 pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="default" className="capitalize">{state.screen_type ?? "unknown"}</Badge>
          {state.ante && <Badge variant="outline">Ante {state.ante}</Badge>}
          {state.confidence != null && (
            <Badge variant="outline">Conf {Math.round((state.confidence ?? 0) * 100)}%</Badge>
          )}
        </div>
        {state.low_confidence && (
          <Badge variant="destructive">Low confidence</Badge>
        )}
      </CardHeader>

      <CardContent className="space-y-3">
        {(state.resources?.hands != null || state.resources?.discards != null || state.resources?.money != null) && (
          <Section title="Resources">
            <div className="flex flex-wrap gap-2">
              {state.resources?.hands != null && <Badge variant="outline">Hands: {state.resources.hands}</Badge>}
              {state.resources?.discards != null && <Badge variant="outline">Discards: {state.resources.discards}</Badge>}
              {state.resources?.money != null && <Badge variant="secondary">${state.resources.money}</Badge>}
            </div>
          </Section>
        )}

        {(state.blind?.target || state.score?.current != null) && (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {state.blind?.target && (
              <Section title="Blind">
                <p className="font-heading text-xs text-foreground">
                  {state.blind?.name ? `${state.blind.name} · ` : ""}
                  {Number(state.blind.target).toLocaleString()} chips
                </p>
              </Section>
            )}
            {state.score?.current != null && (
              <Section title="Score">
                <p className="font-heading text-xs text-foreground">
                  {Number(state.score.current).toLocaleString()}
                </p>
              </Section>
            )}
          </div>
        )}

        {state.jokers?.length > 0 && (
          <Section title={`Jokers (${state.jokers.length})`}>
            <div className="flex flex-wrap gap-2">
              {state.jokers.map((j, i) => (
                <Badge key={i} className="bg-primary/15 text-primary hover:bg-primary/20">
                  {j.name || `Joker ${i + 1}`}
                </Badge>
              ))}
            </div>
          </Section>
        )}

        {state.hand?.length > 0 && (
          <Section title={`Hand (${state.hand.length})`}>
            <div className="flex flex-wrap gap-2">
              {state.hand.map((c, i) => {
                const tone = suitTone[c.suit] ?? "border-border text-foreground";
                return (
                  <span
                    key={i}
                    className={`inline-flex items-center rounded-md border px-2 py-1 text-xs font-semibold ${tone}`}
                  >
                    {c.rank ?? "?"}
                    {suitSymbol[c.suit] ?? "?"}
                  </span>
                );
              })}
            </div>
          </Section>
        )}

        {state.consumables?.length > 0 && (
          <Section title="Consumables">
            <div className="flex flex-wrap gap-2">
              {state.consumables.map((c, i) => (
                <Badge key={i} variant="outline">
                  {c.type}: {c.name || "Unknown"}
                </Badge>
              ))}
            </div>
          </Section>
        )}

        {state.shop?.items?.length > 0 && (
          <Section title={`Shop (${state.shop.items.length})`}>
            <div className="flex flex-wrap gap-2">
              {state.shop.items.map((item, i) => (
                <Badge key={i} variant="secondary">
                  {item.type}: {item.name || "Unknown"}
                </Badge>
              ))}
            </div>
          </Section>
        )}
      </CardContent>
    </Card>
  );
}

function Section({ title, children }) {
  return (
    <div className="rounded-md border border-border/80 bg-muted/20 p-3">
      <CardTitle className="mb-2 text-[0.66rem] uppercase tracking-wide text-muted-foreground">
        {title}
      </CardTitle>
      {children}
    </div>
  );
}
