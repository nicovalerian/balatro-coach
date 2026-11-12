/** @type {import('tailwindcss').Config} */
const rgb = (name) => `rgb(var(--${name}) / <alpha-value>)`;

module.exports = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Balatro palette, driven by the RGB triplets in index.css
        ink: {
          DEFAULT: rgb("ink"),
          muted: rgb("ink-muted"),
          subtle: rgb("ink-subtle"),
        },
        gold: { DEFAULT: rgb("gold"), soft: rgb("gold-soft") },
        chips: rgb("chips"),
        mult: rgb("mult"),
        sky: rgb("sky"),
        felt: { glow: rgb("felt-glow") },
        suit: {
          heart: rgb("suit-heart"),
          diamond: rgb("suit-diamond"),
          club: rgb("suit-club"),
          spade: rgb("suit-spade"),
        },
        line: {
          DEFAULT: "rgb(255 255 255 / 0.1)",
          strong: "rgb(255 255 255 / 0.18)",
        },
      },
      borderRadius: {
        shell: "var(--radius-shell)",
        panel: "var(--radius-panel)",
        control: "var(--radius-control)",
        lg: "var(--radius-panel)",
        md: "var(--radius-control)",
        sm: "calc(var(--radius-control) - 4px)",
      },
      fontFamily: {
        sans: ["JetBrains Mono Variable", "JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
        mono: ["JetBrains Mono Variable", "JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
        pixel: ["M6x11plus", "JetBrains Mono Variable", "monospace"],
      },
      transitionTimingFunction: {
        out: "var(--ease-out)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
