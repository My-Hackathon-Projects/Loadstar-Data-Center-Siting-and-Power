/**
 * Single source of truth for journey timing and copy. Every duration, narrative
 * line, and camera target lives here so the cinematic pacing is tuned in one
 * place. The silent intro is carried by motion and text, so this file is, in
 * effect, the screenplay.
 */

/** Centered narrative lines shown over the starfield, in order. */
export const NARRATIVE_LINES = [
  "our entire history is two things",
  "energy and data",
  "fire and knowledge",
  "we are building their synthesis",
] as const;

export const NARRATIVE_LINE_MS = 2200;
export const NARRATIVE_FADE_S = 0.85;
export const FINAL_NARRATIVE_FADE_S = 1.45;

/**
 * Final-line reveal cadence. The last line types out character-by-character,
 * settles, and only then hands off to the globe. Today the line snapped in at
 * the same fade rate as the others and the globe transition felt like a cut.
 */
export const FINAL_NARRATIVE_CHAR_MS = 65;
export const FINAL_NARRATIVE_REVEAL_BUFFER_MS = 250;
export const FINAL_NARRATIVE_SETTLE_MS = 2500;

const FINAL_NARRATIVE_LINE_LENGTH = Array.from(
  NARRATIVE_LINES[NARRATIVE_LINES.length - 1] ?? "",
).length;

export const FINAL_NARRATIVE_TOTAL_MS =
  FINAL_NARRATIVE_REVEAL_BUFFER_MS +
  FINAL_NARRATIVE_LINE_LENGTH * FINAL_NARRATIVE_CHAR_MS +
  FINAL_NARRATIVE_SETTLE_MS;

/** Per-phase durations (ms). The greeting is command-gated, not timer-gated. */
export const JOURNEY_TIMING = {
  flightMs:
    NARRATIVE_LINE_MS * Math.max(NARRATIVE_LINES.length - 1, 0) +
    FINAL_NARRATIVE_TOTAL_MS,
  arrivalMs: 5500,
} as const;

export const PRODUCT_NAME = "loadstar";
export const FRED_GREETING = "Hello, my name is Fred. How can I help you today?";
export const FRED_QUICK_ACK = "Sure, here is the result.";

/** Starfield: one BufferGeometry, additive blending, a single draw call. */
export const STARFIELD = {
  count: 4200,
  spreadXY: 420,
  depth: 620,
  /** Past this z the star is behind the camera and recycles far ahead. */
  recycleZ: 6,
  /** Forward speed (world units/sec), easing from intense to gentle. */
  speedMax: 235,
  speedMin: 55,
} as const;

/** MapLibre globe view the arrival opens on (whole Earth from space). */
export const GLOBE_VIEW = {
  longitude: 12,
  latitude: 28,
  zoom: 1.25,
  pitch: 0,
  bearing: 0,
} as const;

/** Settled frame holding the European continent (also the reduced-motion view). */
export const EUROPE_VIEW = {
  longitude: 10,
  latitude: 50,
  zoom: 3.4,
  pitch: 0,
  bearing: 0,
} as const;

/** Scripted flyTo chain: clouds-level, then Europe, then settle. */
export const FLY_CHAIN: ReadonlyArray<{
  center: [number, number];
  zoom: number;
  duration: number;
}> = [
  { center: [12, 44], zoom: 2.2, duration: 2600 },
  { center: [10, 50], zoom: 3.4, duration: 2600 },
];

/** framer-motion easing — slow ease-out, nothing bounces. */
export const EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1];
export const CROSSFADE_S = 0.9;
