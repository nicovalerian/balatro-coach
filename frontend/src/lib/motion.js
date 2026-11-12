// Shared motion vocabulary. Mirrors the CSS tokens in index.css
// (--ease-out, --dur-*). Every animated component pulls from here.

export const EASE_OUT = [0.16, 1, 0.3, 1];

// Snappy, lightly damped: used for anything that enters or changes size.
export const SPRING = { type: "spring", stiffness: 420, damping: 36, mass: 0.9 };

export const FADE = { duration: 0.2, ease: EASE_OUT };

// A card being dealt onto the table: rises a few pixels and settles.
export const dealIn = {
  initial: { opacity: 0, y: 12, scale: 0.985 },
  animate: { opacity: 1, y: 0, scale: 1 },
  exit: { opacity: 0, scale: 0.96, transition: FADE },
};

// Disclosure/expandable height animation.
export const collapse = {
  expanded: { height: "auto", opacity: 1 },
  collapsed: { height: 0, opacity: 0 },
};
