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
export const FINAL_NARRATIVE_HOLD_MS = 3600;
export const NARRATIVE_FADE_S = 0.85;
export const FINAL_NARRATIVE_FADE_S = 1.45;

/** Per-phase durations (ms). The greeting is command-gated, not timer-gated. */
export const JOURNEY_TIMING = {
  flightMs:
    NARRATIVE_LINE_MS * Math.max(NARRATIVE_LINES.length - 1, 0) +
    FINAL_NARRATIVE_HOLD_MS,
  arrivalMs: 5500,
} as const;

export const PRODUCT_NAME = "loadstar";
export const FRED_GREETING = "Hello, my name is Fred. How can I help you today?";

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
