/**
 * Loadstar color tokens for non-CSS contexts: Deck.GL RGBA arrays, Recharts
 * stroke strings, and MapLibre style colors.
 *
 * This file and styles/tokens.css are the single source of color truth. No
 * other module may contain raw color literals. Keep the two files in sync; the
 * hex values here mirror the custom properties in tokens.css (opaque
 * approximations are used where a CSS token is translucent, so map and chart
 * strokes stay legible on the dark basemap).
 */

export type Rgb = readonly [number, number, number];
export type Rgba = readonly [number, number, number, number];

/** Hex/string colors for Recharts axes and series, and MapLibre style paint. */
export const COLOR = {
  bgVoid: "#070b14",
  bgPanel: "#0e1422",
  bgPanelRaised: "#131b2c",
  borderSubtle: "#1d2638",
  textPrimary: "#eaeef6",
  textDim: "#79839a",
  accent: "#f4a14e",
  positive: "#5fae87",
  warning: "#d8a13f",
  rampLow: "#d85c48",
  rampMid: "#e0a84e",
  rampHigh: "#3eb296",
} as const;

/** Map data-ramp stops (low -> high), harmonized against the dark basemap. */
export const RAMP_STOPS = {
  low: [216, 92, 72],
  mid: [224, 168, 78],
  high: [62, 178, 150],
} as const satisfies Record<"low" | "mid" | "high", Rgb>;

/** Deck.GL H3 overlay colors (RGB; alpha applied at the call site). */
export const MAP_RGB = {
  accent: [244, 161, 78],
  white: [255, 255, 255],
  highlight: [62, 178, 150],
} as const satisfies Record<string, Rgb>;

/** Recharts series colors keyed to the dispatch chart's semantic sources. */
export const CHART_SERIES = {
  load: COLOR.textPrimary,
  grid: COLOR.textDim,
  clean: COLOR.rampHigh,
  battery: COLOR.accent,
  backup: COLOR.rampLow,
  cost: COLOR.accent,
} as const;
