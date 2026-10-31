/** Explain-mode captions (SPEC 9.7). Edit the wording here without touching components. */
export const EXPLAIN: Record<string, string> = {
  routingRiver: "Each dot is one AI call. SMALL = cheap model, LARGE = stronger model, ROUTED = Prune swapped in a cheaper model, gold CACHE = Prune reused an answer we'd already paid for.",
  counts: "Counted by plain code, not AI, so they're always exact.",
  template: "AI was unavailable or over budget, so standard text was used. Alerts never depend on AI.",
  timeline: "Each event is chained to the one before and signed. Editing one breaks the chain.",
  costMeters: "Left: Prune's own estimate without its optimisations (list price). Right: what we actually paid.",
  heat: "Dots per 25 m square. Red means the area is near or over its safe capacity.",
  quiet: "Orange dots haven't checked in for a while. They may just have no signal.",
  receipts: "Every AI call has a receipt signed by Prune. Anyone can verify it on withprune.com/verify.",
  breakit: "Each trick is a real way people try to cheat or abuse safety systems.",
};
