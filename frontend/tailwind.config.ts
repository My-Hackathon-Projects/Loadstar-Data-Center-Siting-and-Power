import type { Config } from "tailwindcss";

// Semantic color names map to the CSS custom properties in
// src/styles/tokens.css. Components use only these tokens (bg-void, bg-panel,
// text-primary, text-dim, text-accent, ...); raw palette classes
// (bg-slate-*, text-cyan-*, ...) and hex literals must not appear elsewhere.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: "var(--bg-void)",
        panel: "var(--bg-panel)",
        "panel-raised": "var(--bg-panel-raised)",
        subtle: "var(--border-subtle)",
        strong: "var(--border-strong)",
        primary: "var(--text-primary)",
        dim: "var(--text-dim)",
        faint: "var(--text-faint)",
        accent: "var(--accent)",
        "accent-strong": "var(--accent-strong)",
        "accent-contrast": "var(--accent-contrast)",
        positive: "var(--positive)",
        warning: "var(--warning)",
        danger: "var(--danger)",
        scrim: "var(--scrim)",
        thanks: "var(--thanks-bg)",
        "thanks-text": "var(--thanks-text)",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.125rem",
      },
    },
  },
  plugins: [],
} satisfies Config;
